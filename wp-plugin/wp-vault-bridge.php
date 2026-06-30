<?php
/**
 * Plugin Name: WP Vault Bridge
 * Plugin URI: https://github.com/farshadabolfathi/wp-backup-vault
 * Description: Secure WordPress backup plugin with pull-based API for SafeKeep Windows client.
 * Version: 1.0.0
 * Author: Farshad Abolfathi
 * Author URI: https://www.linkedin.com/in/farshad-abolfathi/
 * License: MIT
 * Text Domain: wp-vault-bridge
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
        'WP Vault Bridge',
        'WP Vault Bridge',
        'manage_options',
        'wp-vault-bridge',
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
