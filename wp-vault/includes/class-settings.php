<?php
/** WP Vault — Settings Manager
 * Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
 */

if (!defined('ABSPATH')) exit;

class WVB_Settings {

    const OPT_API_KEY    = 'wvb_api_key';
    const OPT_SCHEDULE   = 'wvb_schedule_times';
    const OPT_RETENTION  = 'wvb_retention_count';
    const OPT_CHUNK_SIZE = 'wvb_chunk_size_mb';
    const OPT_LOG        = 'wvb_backup_log';

    public function get_api_key() {
        return get_option('wvb_api_key', '');
    }

    public function regenerate_api_key() {
        $key = wp_generate_password(32, false);
        update_option('wvb_api_key', $key);
        return $key;
    }

    public function get_schedule_times() {
        $val = get_option('wvb_schedule_times', '["02:00"]');
        return json_decode($val, true) ?: ['02:00'];
    }

    public function set_schedule_times(array $times) {
        $valid = [];
        foreach ($times as $t) {
            if (preg_match('/^\d{2}:\d{2}$/', $t)) {
                $valid[] = $t;
            }
        }
        update_option('wvb_schedule_times', json_encode(array_values($valid)));
    }

    public function get_retention_count() {
        return (int)get_option('wvb_retention_count', 2);
    }

    public function set_retention_count(int $count) {
        update_option('wvb_retention_count', max(1, $count));
    }

    public function get_chunk_size_mb() {
        return (int)get_option('wvb_chunk_size_mb', 50);
    }

    public function set_chunk_size_mb(int $size) {
        update_option('wvb_chunk_size_mb', max(10, min(200, $size)));
    }

    public function append_log(string $message) {
        $log = get_option('wvb_backup_log', '');
        $entry = '[' . date('Y-m-d H:i:s') . '] ' . $message . "\n";
        $lines = array_filter(explode("\n", $log . $entry));
        if (count($lines) > 200) {
            $lines = array_slice($lines, -200);
        }
        update_option('wvb_backup_log', implode("\n", $lines));
        file_put_contents(WVB_PLUGIN_DIR . 'wp-vault.log', $entry, FILE_APPEND | LOCK_EX);
    }

    public function get_log(int $lines = 50) {
        $log = get_option('wvb_backup_log', '');
        $all = array_filter(explode("\n", $log));
        return implode("\n", array_slice($all, -$lines));
    }

    public function save_settings_from_post() {
        check_admin_referer('wvb_save_settings');
        if (!current_user_can('manage_options')) return false;
        if (isset($_POST['chunk_size_mb'])) {
            $this->set_chunk_size_mb((int)$_POST['chunk_size_mb']);
        }
        if (isset($_POST['retention_count'])) {
            $this->set_retention_count((int)$_POST['retention_count']);
        }
        if (isset($_POST['schedule_times'])) {
            $raw = $_POST['schedule_times'];
            if (is_array($raw)) {
                $times = array_map('sanitize_text_field', $raw);
            } else {
                $times = json_decode(stripslashes($raw), true) ?: [];
            }
            if (is_array($times)) {
                $this->set_schedule_times($times);
            }
        }
        (new WVB_Scheduler())->reschedule();
        return true;
    }
}
