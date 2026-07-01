<?php
/**
 * Plugin Name: WP Vault
 * Plugin URI: https://github.com/farshadabolfathi/wp-backup-vault
 * Description: Secure WordPress backup plugin with pull-based API for SafeKeep Windows client.
 * Version: 1.0.0
 * Author: Farshad Abolfathi
 * Author URI: https://www.linkedin.com/in/farshad-abolfathi/
 * License: MIT
 * Text Domain: wp-vault
 *
 * Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
 */

if ( ! defined( 'ABSPATH' ) ) exit;

define( 'WVB_VERSION', '1.0.0' );
define( 'WVB_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'WVB_PLUGIN_URL', plugin_dir_url( __FILE__ ) );
define( 'WVB_BACKUPS_DIR', WVB_PLUGIN_DIR . 'backups/' );

require_once WVB_PLUGIN_DIR . 'includes/class-settings.php';
require_once WVB_PLUGIN_DIR . 'includes/class-backup-engine.php';
require_once WVB_PLUGIN_DIR . 'includes/class-scheduler.php';
require_once WVB_PLUGIN_DIR . 'includes/class-api.php';
require_once WVB_PLUGIN_DIR . 'includes/class-retention.php';

register_activation_hook( __FILE__, 'wvb_activate' );
register_deactivation_hook( __FILE__, 'wvb_deactivate' );

function wvb_activate() {
    if ( ! file_exists( WVB_BACKUPS_DIR ) ) {
        wp_mkdir_p( WVB_BACKUPS_DIR );
    }
    $htaccess = WVB_BACKUPS_DIR . '.htaccess';
    if ( ! file_exists( $htaccess ) ) {
        file_put_contents( $htaccess, "Order deny,allow\nDeny from all\n" );
    }
    $settings = new WVB_Settings();
    if ( ! $settings->get_api_key() ) {
        $settings->regenerate_api_key();
    }
    $scheduler = new WVB_Scheduler();
    $scheduler->schedule_backups();
}

function wvb_deactivate() {
    $scheduler = new WVB_Scheduler();
    $scheduler->unschedule_all();
}

add_action( 'admin_menu', function() {
    add_menu_page(
        'WP Vault',
        'WP Vault',
        'manage_options',
        'wp-vault',
        'wvb_render_admin_page',
        'dashicons-vault',
        80
    );
} );

function wvb_render_admin_page() {
    require_once WVB_PLUGIN_DIR . 'admin/admin-page.php';
}

add_action( 'rest_api_init', function() {
    $api = new WVB_API();
    $api->register_routes();
} );

add_action( 'admin_enqueue_scripts', function( $hook ) {
    require_once WVB_PLUGIN_DIR . 'admin/admin-assets.php';
    wvb_enqueue_admin_assets( $hook );
} );

add_action( 'wp_ajax_wvb_start_backup', function() {
    check_ajax_referer( 'wvb_nonce', 'nonce' );
    if ( ! current_user_can( 'manage_options' ) ) {
        wp_send_json_error( array( 'message' => 'Unauthorized' ) );
    }
    $engine = new WVB_Backup_Engine();
    $backup_id = $engine->start_backup();
    wp_send_json_success( array( 'backup_id' => $backup_id ) );
} );

add_action( 'wp_ajax_wvb_get_progress', function() {
    check_ajax_referer( 'wvb_nonce', 'nonce' );
    if ( ! current_user_can( 'manage_options' ) ) {
        wp_send_json_error( array( 'message' => 'Unauthorized' ) );
    }
    $backup_id = sanitize_text_field( $_GET['backup_id'] ?? '' );
    $engine = new WVB_Backup_Engine();
    $status = $engine->get_backup_status( $backup_id );
    wp_send_json_success( $status );
} );

add_action( 'wp_ajax_wvb_process_step', function() {
    check_ajax_referer( 'wvb_nonce', 'nonce' );
    if ( ! current_user_can( 'manage_options' ) ) {
        wp_send_json_error( array( 'message' => 'Unauthorized' ) );
    }
    $backup_id = sanitize_text_field( $_POST['backup_id'] ?? '' );
    $engine = new WVB_Backup_Engine();
    $result = $engine->process_step( $backup_id );
    wp_send_json_success( $result );
} );

/**
 * WP-Cron fallback: fires on every admin page load.
 * If a scheduled backup time has passed today and no backup exists for today,
 * trigger the backup immediately so low-traffic / overnight schedules don't get skipped.
 */
add_action( 'admin_init', function() {
    if ( ! current_user_can( 'manage_options' ) ) return;
    // Run at most once per hour to avoid hammering on every page load
    if ( get_transient( 'wvb_cron_fallback_checked' ) ) return;
    set_transient( 'wvb_cron_fallback_checked', 1, HOUR_IN_SECONDS );

    $settings = new WVB_Settings();
    $times    = $settings->get_schedule_times();
    $now      = current_time( 'timestamp' );
    $today    = date( 'Y-m-d', $now );
    $now_hm   = date( 'H:i', $now );

    foreach ( $times as $slot ) {
        // Only act if we're past the scheduled time today
        if ( strcmp( $now_hm, $slot ) < 0 ) continue;

        // Check if a backup already completed today for this slot
        $last_key = 'wvb_last_backup_' . str_replace( ':', '', $slot );
        $last_run = get_option( $last_key, '' );
        if ( $last_run === $today ) continue;

        // No backup yet for today at this slot — run it now
        $settings->append_log( 'CronFallback: triggering missed backup for slot ' . $slot );
        update_option( $last_key, $today );

        // Spawn async via loopback HTTP so it doesn't block the admin page
        wp_remote_post( admin_url( 'admin-ajax.php' ), [
            'timeout'   => 1,
            'blocking'  => false,
            'body'      => [
                'action'    => 'wvb_run_scheduled_backup',
                'slot'      => $slot,
                'secret'    => get_option( 'wvb_api_key', '' ),
            ],
            'sslverify' => false,
        ] );
    }
} );

// Handler for the async loopback request
add_action( 'wp_ajax_nopriv_wvb_run_scheduled_backup', 'wvb_handle_scheduled_backup' );
add_action( 'wp_ajax_wvb_run_scheduled_backup',        'wvb_handle_scheduled_backup' );
function wvb_handle_scheduled_backup() {
    $api_key = sanitize_text_field( $_POST['secret'] ?? '' );
    $stored  = get_option( 'wvb_api_key', '' );
    if ( empty( $api_key ) || ! hash_equals( $stored, $api_key ) ) {
        wp_die( 'Unauthorized', 403 );
    }
    $slot = sanitize_text_field( $_POST['slot'] ?? '' );
    $scheduler = new WVB_Scheduler();
    $scheduler->do_backup( $slot );
    wp_die( 'ok' );
}
