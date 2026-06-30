<?php
/** WP Vault — Retention Manager
 * Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
 */

if (!defined('ABSPATH')) exit;

class WVB_Retention {

    public static function run_retention(string $just_completed_id) {
        $settings        = new WVB_Settings();
        $retention_count = $settings->get_retention_count();
        $engine          = new WVB_Backup_Engine();
        $all_backups     = $engine->get_all_backups();

        $complete = array_filter($all_backups, fn($b) => ($b['status'] ?? '') === 'complete');
        $complete = array_values($complete);

        // Sort oldest first
        usort($complete, fn($a, $b) => strcmp($a['date'], $b['date']));

        $to_delete = array_slice($complete, 0, max(0, count($complete) - $retention_count));
        $to_delete = array_filter($to_delete, fn($b) => $b['backup_id'] !== $just_completed_id);

        foreach ($to_delete as $b) {
            $engine->delete_backup($b['backup_id']);
            $settings->append_log('Retention: deleted old backup ' . $b['backup_id']);
        }

        $settings->append_log('Retention: kept up to ' . $retention_count . ' most recent backups');
    }
}
