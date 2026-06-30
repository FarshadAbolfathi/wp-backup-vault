<?php
/**
 * Admin Assets — WP Vault Bridge
 * Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
 */
if ( ! defined( 'ABSPATH' ) ) exit;

function wvb_enqueue_admin_assets( $hook ) {
    if ( 'toplevel_page_wp-vault-bridge' !== $hook ) {
        return;
    }
    wp_enqueue_style(
        'wvb-admin-css',
        WVB_PLUGIN_URL . 'assets/admin.css',
        array(),
        WVB_VERSION
    );
    wp_enqueue_script(
        'wvb-admin-js',
        WVB_PLUGIN_URL . 'assets/admin.js',
        array( 'jquery' ),
        WVB_VERSION,
        true
    );
    wp_localize_script( 'wvb-admin-js', 'wvbData', array(
        'ajax_url'        => admin_url( 'admin-ajax.php' ),
        'nonce'           => wp_create_nonce( 'wvb_nonce' ),
        'rest_url'        => rest_url( 'wp-vault-bridge/v1/' ),
        'rest_nonce'      => wp_create_nonce( 'wp_rest' ),
        'strings'         => array(
            'backup_started'   => 'بک‌آپ شروع شد...',
            'backup_complete'  => 'بک‌آپ با موفقیت انجام شد!',
            'backup_failed'    => 'خطا در انجام بک‌آپ',
            'copied'           => 'کپی شد!',
            'confirm_regen'    => 'آیا از بازتولید کلید API اطمینان دارید؟ کلید قبلی دیگر کار نخواهد کرد.',
            'confirm_delete'   => 'آیا از حذف این بک‌آپ اطمینان دارید؟',
        ),
    ) );
}
