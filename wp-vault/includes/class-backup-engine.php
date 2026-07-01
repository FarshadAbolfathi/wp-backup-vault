<?php
/** WP Vault — Backup Engine
 * Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
 */

if (!defined('ABSPATH')) exit;

class WVB_Backup_Engine {

    private $settings;
    private $backup_dir;

    public function __construct() {
        $this->settings   = new WVB_Settings();
        $this->backup_dir = WVB_BACKUPS_DIR;
    }

    public function start_backup() {
        $backup_id  = date('YmdHis') . '_' . substr(md5(uniqid()), 0, 8);
        $backup_dir = WVB_BACKUPS_DIR . $backup_id . '/';
        wp_mkdir_p($backup_dir);
        update_option(
            'wvb_backup_status_' . $backup_id,
            json_encode([
                'id'      => $backup_id,
                'status'  => 'running',
                'step'    => 'init',
                'progress' => 0,
                'started' => current_time('mysql'),
            ])
        );
        set_transient('wvb_step_' . $backup_id, ['step' => 'init'], HOUR_IN_SECONDS * 2);
        return $backup_id;
    }

    public function process_step($backup_id) {
        $state = get_transient('wvb_step_' . $backup_id);
        if (!$state) {
            return ['error' => 'not found'];
        }

        $result = [];

        switch ($state['step']) {
            case 'init':
                $new_step = 'export_db';
                set_transient('wvb_step_' . $backup_id, ['step' => $new_step], HOUR_IN_SECONDS * 2);
                $result = ['step' => 'export_db', 'progress' => 5];
                break;

            case 'export_db':
                $this->export_database($backup_id);
                $new_step = 'collect_files';
                set_transient('wvb_step_' . $backup_id, ['step' => $new_step], HOUR_IN_SECONDS * 2);
                $result = ['step' => 'collect_files', 'progress' => 20];
                break;

            case 'collect_files':
                $this->collect_files($backup_id);
                $new_step = 'chunk_files';
                set_transient('wvb_step_' . $backup_id, ['step' => $new_step], HOUR_IN_SECONDS * 2);
                $result = ['step' => 'chunk_files', 'progress' => 40];
                break;

            case 'chunk_files':
                $this->chunk_files($backup_id);
                $new_step = 'write_manifest';
                set_transient('wvb_step_' . $backup_id, ['step' => $new_step], HOUR_IN_SECONDS * 2);
                $result = ['step' => 'write_manifest', 'progress' => 80];
                break;

            case 'write_manifest':
                $this->write_manifest($backup_id);
                $this->update_status($backup_id, ['status' => 'complete']);
                if (class_exists('WVB_Retention')) {
                    WVB_Retention::run_retention($backup_id);
                }
                $result = ['step' => 'complete', 'progress' => 100];
                break;

            default:
                $result = ['step' => $state['step'], 'progress' => 0];
                break;
        }

        return $result;
    }

    public function export_database($backup_id) {
        global $wpdb;
        $backup_dir = WVB_BACKUPS_DIR . $backup_id . '/';
        $sql_file   = $backup_dir . 'db-export.sql';
        $gz_file    = $backup_dir . 'db-export.sql.gz';

        // Pure-PHP export — shell functions are disabled on many shared hosts
        $fp = fopen($sql_file, 'w');
        if (!$fp) {
            $this->log('export_database: cannot open ' . $sql_file);
            return;
        }

        fwrite($fp, "-- WP Vault DB Export\n");
        fwrite($fp, "-- Generated: " . date('Y-m-d H:i:s') . "\n\n");
        fwrite($fp, "SET FOREIGN_KEY_CHECKS=0;\n\n");

        $tables = $wpdb->get_results('SHOW TABLES', ARRAY_N);
        foreach ($tables as $row) {
            $table  = $row[0];
            $create = $wpdb->get_row("SHOW CREATE TABLE `{$table}`", ARRAY_N);
            if ($create) {
                fwrite($fp, "DROP TABLE IF EXISTS `{$table}`;\n");
                fwrite($fp, $create[1] . ";\n\n");
            }
            $offset = 0;
            $batch  = 200;
            do {
                $rows = $wpdb->get_results(
                    $wpdb->prepare("SELECT * FROM `{$table}` LIMIT %d OFFSET %d", $batch, $offset),
                    ARRAY_A
                );
                if (empty($rows)) break;
                $columns = '`' . implode('`, `', array_keys($rows[0])) . '`';
                foreach ($rows as $row_data) {
                    $values = array_map(function ($v) use ($wpdb) {
                        if ($v === null) return 'NULL';
                        return "'" . $wpdb->_escape($v) . "'";
                    }, array_values($row_data));
                    fwrite($fp, "INSERT INTO `{$table}` ({$columns}) VALUES (" . implode(', ', $values) . ");\n");
                }
                $offset += $batch;
            } while (count($rows) === $batch);
            fwrite($fp, "\n");
        }

        fwrite($fp, "SET FOREIGN_KEY_CHECKS=1;\n");
        fclose($fp);

        // Gzip in chunks to avoid loading the whole SQL into memory
        if (file_exists($sql_file) && filesize($sql_file) > 0) {
            $gz = gzopen($gz_file, 'wb6');
            if ($gz) {
                $in = fopen($sql_file, 'rb');
                while (!feof($in)) {
                    gzwrite($gz, fread($in, 65536));
                }
                fclose($in);
                gzclose($gz);
                unlink($sql_file);
            } else {
                // gzip unavailable — keep the plain .sql
                rename($sql_file, $backup_dir . 'db-export.sql');
                $gz_file = $backup_dir . 'db-export.sql';
            }
        }

        $this->log('Database exported: ' . basename($gz_file));
    }

    public function collect_files($backup_id) {
        $files       = [];
        $content_dir = WP_CONTENT_DIR;

        // Directories to skip (cache, logs, temp, and our own backup folder)
        $skip_dirnames = [
            'cache', 'et-cache', 'wc-logs', 'woocommerce_uploads', 'wpml',
            'backups', 'backup', 'updraft', 'wp-rocket-cache', 'wp-cache',
            '.git', '.svn', 'node_modules', 'tmp', 'temp',
        ];

        $exclude_real = [];
        $real_backup  = realpath(WVB_BACKUPS_DIR);
        if ($real_backup) $exclude_real[] = $real_backup;

        try {
            $dir_iter = new RecursiveDirectoryIterator(
                $content_dir,
                RecursiveDirectoryIterator::SKIP_DOTS | RecursiveDirectoryIterator::FOLLOW_SYMLINKS
            );
            $iter = new RecursiveIteratorIterator(
                $dir_iter,
                RecursiveIteratorIterator::SELF_FIRST
            );
            $iter->setMaxDepth(10);

            foreach ($iter as $file) {
                if ($file->isDir()) {
                    $base = strtolower($file->getBasename());
                    if (in_array($base, $skip_dirnames, true)) {
                        $iter->getInnerIterator()->rewind();
                        $iter->next();
                        continue;
                    }
                    continue;
                }

                if (!$file->isFile() || !$file->isReadable()) continue;

                $path      = $file->getPathname();
                $real_path = realpath($path) ?: $path;

                // Skip files inside excluded directories
                $skip = false;
                foreach ($exclude_real as $ex) {
                    if (strpos($real_path, $ex) === 0) { $skip = true; break; }
                }
                if ($skip) continue;

                // Skip files > 500 MB
                if ($file->getSize() > 500 * 1024 * 1024) continue;

                $files[] = $path;
            }
        } catch (Exception $e) {
            $this->log('collect_files error: ' . $e->getMessage());
        }

        set_transient('wvb_files_' . $backup_id, $files, HOUR_IN_SECONDS * 2);
        $this->log('Collected ' . count($files) . ' files');
        return count($files);
    }

    public function chunk_files($backup_id) {
        $files            = get_transient('wvb_files_' . $backup_id) ?: [];
        $chunk_size_bytes = $this->settings->get_chunk_size_mb() * 1024 * 1024;
        $backup_dir       = WVB_BACKUPS_DIR . $backup_id . '/';
        $gz_db            = $backup_dir . 'db-export.sql.gz';

        $chunks              = [];
        $chunk_num           = 0;
        $current_chunk_size  = 0;
        $current_chunk_files = [];

        // Add DB gz to first chunk
        if (file_exists($gz_db)) {
            $current_chunk_files[] = ['path' => $gz_db, 'relative' => 'db-export.sql.gz', 'is_db' => true];
            $current_chunk_size   += filesize($gz_db);
        }

        foreach ($files as $f) {
            if (!file_exists($f)) continue;
            $size     = filesize($f);
            $relative = ltrim(str_replace(WP_CONTENT_DIR, '', $f), '/');

            if ($current_chunk_size + $size > $chunk_size_bytes && !empty($current_chunk_files)) {
                // Save current chunk
                $chunk_filename = sprintf('chunk-%03d.zip', $chunk_num);
                $chunk_path     = $backup_dir . $chunk_filename;
                $zip            = new ZipArchive();
                if ($zip->open($chunk_path, ZipArchive::CREATE) === true) {
                    foreach ($current_chunk_files as $cf) {
                        if (isset($cf['is_db']) && $cf['is_db']) {
                            $zip->addFile($cf['path'], $cf['relative']);
                        } else {
                            $zip->addFile($cf['path'], 'wp-content/' . $cf['relative']);
                        }
                    }
                    $zip->close();
                }
                $chunks[] = ['filename' => $chunk_filename, 'num_files' => count($current_chunk_files)];
                $chunk_num++;
                $current_chunk_files = [];
                $current_chunk_size  = 0;
            }

            $current_chunk_files[] = ['path' => $f, 'relative' => $relative];
            $current_chunk_size   += $size;
        }

        // Save remaining chunk
        if (!empty($current_chunk_files)) {
            $chunk_filename = sprintf('chunk-%03d.zip', $chunk_num);
            $chunk_path     = $backup_dir . $chunk_filename;
            $zip            = new ZipArchive();
            if ($zip->open($chunk_path, ZipArchive::CREATE) === true) {
                foreach ($current_chunk_files as $cf) {
                    if (isset($cf['is_db']) && $cf['is_db']) {
                        $zip->addFile($cf['path'], $cf['relative']);
                    } else {
                        $zip->addFile($cf['path'], 'wp-content/' . $cf['relative']);
                    }
                }
                $zip->close();
            }
            $chunks[] = ['filename' => $chunk_filename, 'num_files' => count($current_chunk_files)];
        }

        set_transient('wvb_chunks_' . $backup_id, $chunks, HOUR_IN_SECONDS * 2);
        $this->log('Created ' . count($chunks) . ' chunks');
    }

    public function write_manifest($backup_id) {
        global $wp_version;
        $backup_dir     = WVB_BACKUPS_DIR . $backup_id . '/';
        $chunks         = get_transient('wvb_chunks_' . $backup_id) ?: [];
        $manifest_chunks = [];
        $total_size     = 0;

        foreach ($chunks as $c) {
            $file = $backup_dir . $c['filename'];
            if (!file_exists($file)) continue;
            $size        = filesize($file);
            $total_size += $size;
            $manifest_chunks[] = [
                'filename' => $c['filename'],
                'size'     => $size,
                'md5'      => md5_file($file),
                'sha256'   => hash_file('sha256', $file),
            ];
        }

        $manifest = [
            'backup_id'      => $backup_id,
            'date'           => gmdate('c'),
            'site_url'       => get_option('siteurl'),
            'wp_version'     => $wp_version,
            'plugin_version' => WVB_VERSION,
            'total_size'     => $total_size,
            'chunks'         => $manifest_chunks,
        ];

        file_put_contents($backup_dir . 'manifest.json', json_encode($manifest, JSON_PRETTY_PRINT));
        $this->update_status($backup_id, ['status' => 'complete', 'progress' => 100]);
        $this->log('Manifest written, total size: ' . $total_size . ' bytes');
    }

    public function get_backup_status($backup_id) {
        $raw = get_option('wvb_backup_status_' . $backup_id, '');
        if (!$raw) return ['status' => 'not_found'];
        $data = json_decode($raw, true);
        return is_array($data) ? $data : ['status' => 'unknown'];
    }

    public function update_status($backup_id, array $updates) {
        $current = $this->get_backup_status($backup_id);
        if (($current['status'] ?? '') === 'not_found') $current = [];
        $merged = array_merge($current, $updates);
        update_option('wvb_backup_status_' . $backup_id, json_encode($merged));
    }

    public function get_all_backups() {
        $dirs = glob(WVB_BACKUPS_DIR . '*', GLOB_ONLYDIR);
        if (!$dirs) return [];
        $backups = [];
        foreach ($dirs as $d) {
            $manifest_file = $d . '/manifest.json';
            if (!file_exists($manifest_file)) continue;
            $manifest = json_decode(file_get_contents($manifest_file), true);
            if (!is_array($manifest)) continue;
            $status_data       = $this->get_backup_status($manifest['backup_id']);
            $manifest['status'] = $status_data['status'] ?? 'unknown';
            $backups[]         = $manifest;
        }
        usort($backups, fn($a, $b) => strcmp($b['date'], $a['date']));
        return $backups;
    }

    public function delete_backup($backup_id) {
        if (!preg_match('/^[a-zA-Z0-9_]+$/', $backup_id)) return false;
        $dir = WVB_BACKUPS_DIR . $backup_id;
        if (!is_dir($dir)) return false;
        $files = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($dir, RecursiveDirectoryIterator::SKIP_DOTS),
            RecursiveIteratorIterator::CHILD_FIRST
        );
        foreach ($files as $fileinfo) {
            if ($fileinfo->isDir()) {
                rmdir($fileinfo->getRealPath());
            } else {
                unlink($fileinfo->getRealPath());
            }
        }
        rmdir($dir);
        delete_option('wvb_backup_status_' . $backup_id);
        return true;
    }

    private function log($message) {
        $this->settings->append_log('BackupEngine: ' . $message);
    }
}
