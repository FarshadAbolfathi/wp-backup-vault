<?php
/** WP Vault Bridge — REST API
 * Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
 */

if (!defined('ABSPATH')) exit;

class WVB_API {

    public function register_routes() {
        register_rest_route('wp-vault-bridge/v1', '/backups', [
            'methods'             => 'GET',
            'callback'            => [$this, 'get_backups'],
            'permission_callback' => [$this, 'authenticate'],
        ]);

        register_rest_route('wp-vault-bridge/v1', '/backups/(?P<id>[a-zA-Z0-9_]+)/manifest', [
            'methods'             => 'GET',
            'callback'            => [$this, 'get_manifest'],
            'permission_callback' => [$this, 'authenticate'],
        ]);

        register_rest_route('wp-vault-bridge/v1', '/backups/(?P<id>[a-zA-Z0-9_]+)/chunks/(?P<filename>[a-zA-Z0-9_.%+-]+)', [
            'methods'             => 'GET',
            'callback'            => [$this, 'get_chunk'],
            'permission_callback' => [$this, 'authenticate'],
        ]);

        register_rest_route('wp-vault-bridge/v1', '/backups/(?P<id>[a-zA-Z0-9_]+)', [
            'methods'             => 'DELETE',
            'callback'            => [$this, 'delete_backup_route'],
            'permission_callback' => [$this, 'authenticate'],
        ]);

        register_rest_route('wp-vault-bridge/v1', '/generate-key', [
            'methods'             => 'POST',
            'callback'            => [$this, 'generate_key'],
            'permission_callback' => '__return_true',
        ]);
    }

    public function authenticate(WP_REST_Request $request) {
        $ip       = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
        $rate_key = 'wvb_rate_' . md5($ip);
        $count    = (int)get_transient($rate_key);
        if ($count > 60) {
            return new WP_Error('rate_limit', 'Too many requests', ['status' => 429]);
        }
        set_transient($rate_key, $count + 1, 60);

        $api_key = $request->get_header('X-API-Key');
        $stored  = get_option('wvb_api_key', '');
        if (empty($api_key) || !hash_equals($stored, $api_key)) {
            return new WP_Error('unauthorized', 'Invalid API Key', ['status' => 401]);
        }
        return true;
    }

    public function get_backups(WP_REST_Request $request) {
        $engine = new WVB_Backup_Engine();
        return new WP_REST_Response($engine->get_all_backups(), 200);
    }

    public function get_manifest(WP_REST_Request $request) {
        $backup_id = sanitize_text_field($request['id']);
        if (!preg_match('/^[a-zA-Z0-9_]+$/', $backup_id)) {
            return new WP_Error('invalid_id', 'Invalid backup ID', ['status' => 400]);
        }
        $file = WVB_BACKUPS_DIR . $backup_id . '/manifest.json';
        if (!file_exists($file)) {
            return new WP_Error('not_found', 'Backup not found', ['status' => 404]);
        }
        $data = json_decode(file_get_contents($file), true);
        return new WP_REST_Response($data, 200);
    }

    public function get_chunk(WP_REST_Request $request) {
        $backup_id = sanitize_text_field($request['id']);
        $filename  = sanitize_file_name($request['filename']);

        if (!preg_match('/^[a-zA-Z0-9_]+$/', $backup_id)) {
            return new WP_Error('invalid_id', 'Invalid backup ID', ['status' => 400]);
        }
        if (strpos($filename, '..') !== false || strpos($filename, '/') !== false || strpos($filename, '\\') !== false) {
            return new WP_Error('invalid_file', 'Invalid filename', ['status' => 400]);
        }

        $filepath  = WVB_BACKUPS_DIR . $backup_id . '/' . $filename;
        if (!file_exists($filepath)) {
            return new WP_Error('not_found', 'File not found', ['status' => 404]);
        }

        $file_size    = filesize($filepath);
        $range_header = $_SERVER['HTTP_RANGE'] ?? '';

        if (!empty($range_header) && preg_match('/bytes=(\d+)-(\d*)/', $range_header, $m)) {
            $start  = (int)$m[1];
            $end    = isset($m[2]) && $m[2] !== '' ? (int)$m[2] : $file_size - 1;
            $length = $end - $start + 1;
            header('HTTP/1.1 206 Partial Content');
            header('Content-Range: bytes ' . $start . '-' . $end . '/' . $file_size);
            header('Content-Length: ' . $length);
            header('Content-Type: application/octet-stream');
            header('Content-Disposition: attachment; filename="' . basename($filepath) . '"');
            header('Accept-Ranges: bytes');
            $fh   = fopen($filepath, 'rb');
            fseek($fh, $start);
            $sent = 0;
            while ($sent < $length) {
                $chunk = min(8192, $length - $sent);
                echo fread($fh, $chunk);
                $sent += $chunk;
                ob_flush();
                flush();
            }
            fclose($fh);
            exit;
        } else {
            header('HTTP/1.1 200 OK');
            header('Content-Length: ' . $file_size);
            header('Content-Type: application/octet-stream');
            header('Content-Disposition: attachment; filename="' . basename($filepath) . '"');
            header('Accept-Ranges: bytes');
            readfile($filepath);
            exit;
        }
    }

    public function delete_backup_route(WP_REST_Request $request) {
        $backup_id = sanitize_text_field($request['id']);
        $engine    = new WVB_Backup_Engine();
        $result    = $engine->delete_backup($backup_id);
        if ($result) {
            return new WP_REST_Response(['deleted' => true], 200);
        }
        return new WP_Error('delete_failed', 'Could not delete backup', ['status' => 500]);
    }

    public function generate_key(WP_REST_Request $request) {
        $nonce = $request->get_header('X-WP-Nonce');
        if (!wp_verify_nonce($nonce, 'wp_rest')) {
            return new WP_Error('bad_nonce', 'Invalid nonce', ['status' => 403]);
        }
        if (!current_user_can('manage_options')) {
            return new WP_Error('forbidden', 'Insufficient permissions', ['status' => 403]);
        }
        $settings = new WVB_Settings();
        $new_key  = $settings->regenerate_api_key();
        return new WP_REST_Response(['api_key' => substr($new_key, 0, 4) . str_repeat('*', 28)], 200);
    }
}
