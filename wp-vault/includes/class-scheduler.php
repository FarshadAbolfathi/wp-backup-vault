<?php
/** WP Vault — Scheduler
 * Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
 */

if (!defined('ABSPATH')) exit;

class WVB_Scheduler {

    public function __construct() {
        add_action('wvb_run_backup', [$this, 'do_backup'], 10, 1);
    }

    public function schedule_backups() {
        $settings = new WVB_Settings();
        $times    = $settings->get_schedule_times();
        foreach ($times as $time_slot) {
            [$hour, $min] = explode(':', $time_slot);
            $now   = current_time('timestamp');
            $today = mktime((int)$hour, (int)$min, 0, date('n', $now), date('j', $now), date('Y', $now));
            $ts    = ($today > $now) ? $today : $today + DAY_IN_SECONDS;
            if (!wp_next_scheduled('wvb_run_backup', [$time_slot])) {
                wp_schedule_single_event($ts, 'wvb_run_backup', [$time_slot]);
                (new WVB_Settings())->append_log('Scheduler: scheduled ' . $time_slot . ' at ' . date('Y-m-d H:i:s', $ts));
            }
        }
    }

    public function unschedule_all() {
        if (function_exists('wp_unschedule_hook')) {
            wp_unschedule_hook('wvb_run_backup');
        } else {
            $timestamp = wp_next_scheduled('wvb_run_backup');
            while ($timestamp) {
                wp_unschedule_event($timestamp, 'wvb_run_backup');
                $timestamp = wp_next_scheduled('wvb_run_backup');
            }
            // Handle events with args
            $crons = _get_cron_array();
            if (is_array($crons)) {
                foreach ($crons as $time => $hooks) {
                    if (isset($hooks['wvb_run_backup'])) {
                        foreach ($hooks['wvb_run_backup'] as $key => $event) {
                            wp_unschedule_event($time, 'wvb_run_backup', $event['args']);
                        }
                    }
                }
            }
        }
    }

    public function reschedule() {
        $this->unschedule_all();
        $this->schedule_backups();
    }

    public function do_backup($time_slot = '') {
        $engine    = new WVB_Backup_Engine();
        $backup_id = $engine->start_backup();
        $max_steps = 10;
        $i         = 0;
        do {
            $result = $engine->process_step($backup_id);
            $i++;
        } while (($result['step'] ?? '') !== 'complete' && ($result['error'] ?? '') === '' && $i < $max_steps);

        $settings = new WVB_Settings();
        if (($result['step'] ?? '') === 'complete') {
            $settings->append_log('Scheduler: backup ' . $backup_id . ' completed via cron slot ' . $time_slot);
        } else {
            $settings->append_log('Scheduler: backup ' . $backup_id . ' may have stalled at step ' . ($result['step'] ?? 'unknown'));
        }

        // Reschedule for same time tomorrow
        [$hour, $min] = explode(':', $time_slot ?: '02:00');
        $ts = mktime((int)$hour, (int)$min, 0, date('n'), date('j'), date('Y')) + DAY_IN_SECONDS;
        wp_schedule_single_event($ts, 'wvb_run_backup', [$time_slot]);
    }
}
