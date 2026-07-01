<?php
/**
 * WP Vault — Dashboard Widget
 * Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
 */

if ( ! defined( 'ABSPATH' ) ) exit;

function wvb_register_dashboard_widget() {
    wp_add_dashboard_widget(
        'wvb_backup_status_widget',
        '🛡️ WP Vault — وضعیت بک‌آپ',
        'wvb_render_dashboard_widget'
    );
}
add_action( 'wp_dashboard_setup', 'wvb_register_dashboard_widget' );

function wvb_render_dashboard_widget() {
    $engine   = new WVB_Backup_Engine();
    $backups  = $engine->get_all_backups();

    // Find last completed backup
    $last = null;
    foreach ( $backups as $b ) {
        if ( ( $b['status'] ?? '' ) === 'complete' ) {
            $last = $b;
            break; // already sorted newest-first
        }
    }

    $plugin_url = admin_url( 'admin.php?page=wp-vault&wvb_tab=backups' );

    wp_enqueue_style(
        'wvb-dashboard-css',
        WVB_PLUGIN_URL . 'assets/dashboard-widget.css',
        [],
        WVB_VERSION
    );
    ?>
    <a href="<?php echo esc_url( $plugin_url ); ?>" class="wvb-dash-link" title="رفتن به تب بک‌آپ‌ها">
        <div class="wvb-dash-widget <?php echo $last ? 'wvb-dash-ok' : 'wvb-dash-warn'; ?>">

            <div class="wvb-dash-icon">
                <?php echo $last ? '✅' : '⚠️'; ?>
            </div>

            <div class="wvb-dash-body">
                <?php if ( $last ) :
                    // Parse ISO date
                    $ts      = strtotime( $last['date'] );
                    $jalali  = wvb_to_jalali( $ts );
                    $time_fa = wvb_fa_digits( date( 'H:i', $ts ) );
                    $size_mb = isset( $last['total_size'] ) && $last['total_size'] > 0
                               ? round( $last['total_size'] / 1048576, 1 ) . ' MB'
                               : '—';
                    $ago     = wvb_time_ago( $ts );
                ?>
                    <div class="wvb-dash-title">آخرین بک‌آپ کامل</div>
                    <div class="wvb-dash-date"><?php echo esc_html( $jalali ); ?></div>
                    <div class="wvb-dash-time"><?php echo esc_html( $time_fa ); ?></div>
                    <div class="wvb-dash-meta">
                        <span class="wvb-badge wvb-badge-green">✓ موفق</span>
                        <span class="wvb-dash-size"><?php echo esc_html( $size_mb ); ?></span>
                        <span class="wvb-dash-ago"><?php echo esc_html( $ago ); ?></span>
                    </div>
                <?php else : ?>
                    <div class="wvb-dash-title">بک‌آپ کاملی یافت نشد</div>
                    <div class="wvb-dash-date" style="font-size:13px; margin-top:6px;">
                        برای شروع روی این باکس کلیک کنید
                    </div>
                <?php endif; ?>
            </div>

            <div class="wvb-dash-arrow">&#8592;</div>
        </div>
    </a>
    <?php
}

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------

function wvb_to_jalali( $timestamp ) {
    $y = (int) date( 'Y', $timestamp );
    $m = (int) date( 'n', $timestamp );
    $d = (int) date( 'j', $timestamp );

    // Gregorian to Jalali
    $g_days_in_month = [31,28,31,30,31,30,31,31,30,31,30,31];
    $j_days_in_month = [31,31,31,31,31,31,30,30,30,30,30,29];

    $gy = $y - 1600; $gm = $m - 1; $gd = $d - 1;
    $g_day_no = 365 * $gy + (int)(($gy + 3) / 4) - (int)(($gy + 99) / 100) + (int)(($gy + 399) / 400);
    for ( $i = 0; $i < $gm; $i++ ) $g_day_no += $g_days_in_month[$i];
    if ( $gm > 1 && (($gy + 1600) % 4 === 0 && (($gy + 1600) % 100 !== 0 || ($gy + 1600) % 400 === 0)) ) $g_day_no++;
    $g_day_no += $gd;
    $j_day_no = $g_day_no - 79;
    $j_np = (int)($j_day_no / 12053); $j_day_no %= 12053;
    $jy = 979 + 33 * $j_np + 4 * (int)($j_day_no / 1461);
    $j_day_no %= 1461;
    if ( $j_day_no >= 366 ) { $jy += (int)(($j_day_no - 1) / 365); $j_day_no = ($j_day_no - 1) % 365; }
    for ( $i = 0; $i < 11 && $j_day_no >= $j_days_in_month[$i]; $i++ ) $j_day_no -= $j_days_in_month[$i];
    $jm = $i + 1; $jd = $j_day_no + 1;

    $months_fa = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
    return wvb_fa_digits( $jd ) . ' ' . $months_fa[ $jm - 1 ] . ' ' . wvb_fa_digits( $jy );
}

function wvb_fa_digits( $str ) {
    $fa = ['۰','۱','۲','۳','۴','۵','۶','۷','۸','۹'];
    return str_replace( range(0,9), $fa, (string)$str );
}

function wvb_time_ago( $ts ) {
    $diff = time() - $ts;
    if ( $diff < 3600 )     return wvb_fa_digits( (int)($diff / 60) ) . ' دقیقه پیش';
    if ( $diff < 86400 )    return wvb_fa_digits( (int)($diff / 3600) ) . ' ساعت پیش';
    return wvb_fa_digits( (int)($diff / 86400) ) . ' روز پیش';
}
