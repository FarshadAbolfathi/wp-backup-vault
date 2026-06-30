<?php
/**
 * WP Vault — Admin Page
 * Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
 */
if ( ! defined( 'ABSPATH' ) ) exit;

$saved_msg = '';
if ( isset( $_POST['wvb_save_settings'] ) ) {
    ( new WVB_Settings() )->save_settings_from_post();
    $saved_msg = 'تنظیمات ذخیره شد.';
}

$settings       = new WVB_Settings();
$engine         = new WVB_Backup_Engine();
$all_backups    = $engine->get_all_backups();
$api_key        = $settings->get_api_key();
$chunk_size     = $settings->get_chunk_size_mb();
$retention      = $settings->get_retention_count();
$schedule_times = $settings->get_schedule_times();
$log_text       = $settings->get_log( 50 );

$masked_key = ( strlen( $api_key ) >= 4 )
    ? substr( $api_key, 0, 4 ) . '****'
    : '****';
?>
<div class="wvb-wrap" dir="rtl" lang="fa">

    <div class="wvb-header">
        <h1>WP Vault</h1>
    </div>

    <div class="wvb-tabs" id="wvb-tabs">
        <div class="wvb-tab active" data-tab="settings">تنظیمات</div>
        <div class="wvb-tab" data-tab="backups">بک‌آپ‌ها</div>
        <div class="wvb-tab" data-tab="logs">گزارش</div>
    </div>

    <!-- ===================== TAB: تنظیمات ===================== -->
    <div class="wvb-tab-content active" id="tab-settings">

        <?php if ( $saved_msg ) : ?>
            <div class="wvb-notice wvb-notice-success"><?php echo esc_html( $saved_msg ); ?></div>
        <?php endif; ?>

        <div class="wvb-card">
            <h2>تنظیمات عمومی</h2>
            <form method="post" action="">
                <?php wp_nonce_field( 'wvb_save_settings' ); ?>
                <input type="hidden" name="wvb_save_settings" value="1" />

                <table class="wvb-form-table">
                    <tr>
                        <th><label for="chunk_size_mb">حجم هر تکه (مگابایت)</label></th>
                        <td>
                            <input
                                type="number"
                                id="chunk_size_mb"
                                name="chunk_size_mb"
                                value="<?php echo esc_attr( $chunk_size ); ?>"
                                min="1"
                                max="500"
                            />
                        </td>
                    </tr>
                    <tr>
                        <th><label for="retention_count">تعداد بک‌آپ‌های نگهداری‌شده</label></th>
                        <td>
                            <input
                                type="number"
                                id="retention_count"
                                name="retention_count"
                                value="<?php echo esc_attr( $retention ); ?>"
                                min="1"
                                max="100"
                            />
                        </td>
                    </tr>
                    <tr>
                        <th><label>زمان‌بندی بک‌آپ خودکار</label></th>
                        <td>
                            <div class="wvb-schedule-times" id="schedule-times-wrap">
                                <?php
                                $times = is_array( $schedule_times ) ? $schedule_times : array();
                                if ( empty( $times ) ) {
                                    $times = array( '02:00' );
                                }
                                foreach ( $times as $t ) : ?>
                                    <div class="wvb-schedule-row">
                                        <input
                                            type="time"
                                            name="schedule_times[]"
                                            value="<?php echo esc_attr( $t ); ?>"
                                        />
                                        <button type="button" class="wvb-remove-time" title="حذف">&#215;</button>
                                    </div>
                                <?php endforeach; ?>
                            </div>
                            <button type="button" id="add-time-btn" class="wvb-btn wvb-btn-secondary" style="margin-top:8px;">
                                + افزودن زمان
                            </button>
                        </td>
                    </tr>
                </table>

                <p style="margin-top:20px;">
                    <button type="submit" class="wvb-btn wvb-btn-primary">ذخیره تنظیمات</button>
                </p>
            </form>
        </div>

        <div class="wvb-card">
            <h2>کلید API</h2>
            <p>این کلید را در برنامه SafeKeep وارد کنید. هرگز آن را با دیگران به اشتراک نگذارید.</p>
            <div class="wvb-api-key-wrap">
                <span class="wvb-api-key-display" id="api-key-masked"><?php echo esc_html( $masked_key ); ?></span>
                <span id="api-key-full" style="display:none;"><?php echo esc_html( $api_key ); ?></span>
                <button type="button" id="copy-api-key" class="wvb-btn wvb-btn-secondary">کپی کلید</button>
                <button type="button" id="regen-api-key" class="wvb-btn wvb-btn-danger">بازتولید کلید</button>
            </div>
        </div>

    </div><!-- /tab-settings -->

    <!-- ===================== TAB: بک‌آپ‌ها ===================== -->
    <div class="wvb-tab-content" id="tab-backups">

        <div class="wvb-card">
            <h2>بک‌آپ‌ها</h2>

            <p>
                <button type="button" id="start-backup-btn" class="wvb-btn wvb-btn-primary">شروع بک‌آپ</button>
            </p>

            <div id="backup-progress" style="display:none;" class="wvb-progress-wrap">
                <div class="wvb-progress">
                    <div class="wvb-progress-bar" id="wvb-progress-bar" style="width:0%;"></div>
                </div>
            </div>

            <div id="backup-status-msg" class="wvb-notice" style="display:none; margin-top:10px;"></div>

            <hr style="margin:20px 0;" />

            <?php if ( empty( $all_backups ) ) : ?>
                <p style="color:#777; font-style:italic;">بک‌آپی وجود ندارد</p>
            <?php else : ?>
                <table class="wvb-backups-table">
                    <thead>
                        <tr>
                            <th>شناسه</th>
                            <th>تاریخ</th>
                            <th>حجم</th>
                            <th>وضعیت</th>
                            <th>عملیات</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ( $all_backups as $backup ) :
                            $bid        = isset( $backup['backup_id'] ) ? $backup['backup_id'] : '';
                            $bdate      = isset( $backup['date'] )      ? $backup['date']      : '—';
                            $bsize_raw  = isset( $backup['total_size'] ) ? (int) $backup['total_size'] : 0;
                            $bsize_mb   = $bsize_raw > 0 ? round( $bsize_raw / 1048576, 2 ) . ' MB' : '—';
                            $bstatus    = isset( $backup['status'] )    ? $backup['status']    : 'unknown';
                            $badge_class = 'unknown';
                            if ( 'complete' === $bstatus ) {
                                $badge_class = 'complete';
                            } elseif ( 'running' === $bstatus ) {
                                $badge_class = 'running';
                            } elseif ( 'failed' === $bstatus ) {
                                $badge_class = 'failed';
                            }
                        ?>
                            <tr>
                                <td><code><?php echo esc_html( $bid ); ?></code></td>
                                <td><?php echo esc_html( $bdate ); ?></td>
                                <td><?php echo esc_html( $bsize_mb ); ?></td>
                                <td>
                                    <span class="wvb-status-badge <?php echo esc_attr( $badge_class ); ?>">
                                        <?php echo esc_html( $bstatus ); ?>
                                    </span>
                                </td>
                                <td>
                                    <button
                                        type="button"
                                        class="wvb-btn wvb-btn-danger delete-backup-btn"
                                        data-backup-id="<?php echo esc_attr( $bid ); ?>"
                                    >حذف</button>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            <?php endif; ?>
        </div>

    </div><!-- /tab-backups -->

    <!-- ===================== TAB: گزارش ===================== -->
    <div class="wvb-tab-content" id="tab-logs">

        <div class="wvb-card">
            <h2>گزارش رویدادها</h2>
            <pre id="log-content"><?php echo esc_html( $log_text ); ?></pre>
        </div>

    </div><!-- /tab-logs -->

    <div class="wvb-footer">
        توسعه‌یافته توسط <a href="<?php echo esc_url( 'https://www.linkedin.com/in/farshad-abolfathi/' ); ?>">Farshad Abolfathi</a>
    </div>

</div><!-- /.wvb-wrap -->
