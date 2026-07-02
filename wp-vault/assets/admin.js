/* WP Vault — Admin JS
 * Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
 */
(function ($) {
    'use strict';

    $(document).ready(function () {
        initTabs();
        initBackupButton();
        initApiKey();
        initScheduleTimes();
        initDeleteBackup();
    });

    /* ------------------------------------------------------------------ */
    /* Tabs                                                                  */
    /* ------------------------------------------------------------------ */
    function initTabs() {
        $('.wvb-tab').on('click', function () {
            var tab = $(this).data('tab');
            $('.wvb-tab').removeClass('active');
            $('.wvb-tab-content').removeClass('active');
            $(this).addClass('active');
            $('#tab-' + tab).addClass('active');
            localStorage.setItem('wvb_active_tab', tab);
        });

        // If redirected from dashboard widget, open the requested tab
        var urlParams = new URLSearchParams(window.location.search);
        var forcedTab = urlParams.get('wvb_tab');
        if (forcedTab) {
            $('[data-tab="' + forcedTab + '"]').trigger('click');
            return;
        }

        var saved = localStorage.getItem('wvb_active_tab');
        if (saved) {
            $('[data-tab="' + saved + '"]').trigger('click');
        }
    }

    /* ------------------------------------------------------------------ */
    /* Backup Button                                                         */
    /* ------------------------------------------------------------------ */
    function initBackupButton() {
        $('#start-backup-btn').on('click', function () {
            startBackup();
        });
    }

    var pollTimer = null;

    function startBackup() {
        $('#start-backup-btn').prop('disabled', true).text('در حال بک‌آپ...');
        showStatus(wvbData.strings.backup_started, 'info');
        $('#backup-progress').show();
        updateProgress(0, wvbData.strings.backup_started);
        $('.wvb-progress-bar').addClass('animating');

        $.ajax({
            url: wvbData.ajax_url,
            method: 'POST',
            data: { action: 'wvb_start_backup', nonce: wvbData.nonce },
            success: function (res) {
                if (res && res.success && res.data && res.data.backup_id) {
                    // Backup launched in background — start polling for progress
                    pollProgress(res.data.backup_id, 0);
                } else {
                    handleBackupError(res && res.data && res.data.message ? res.data.message : null);
                }
            },
            error: function (xhr) {
                handleBackupError(extractErrorMsg(xhr));
            }
        });
    }

    function pollProgress(backup_id, ticks) {
        if (ticks > 120) { // 120 × 5s = 10 min max
            handleBackupError('تایم‌اوت: بک‌آپ پس از ۱۰ دقیقه کامل نشد');
            return;
        }
        pollTimer = setTimeout(function () {
            $.ajax({
                url: wvbData.ajax_url,
                method: 'POST',
                data: { action: 'wvb_get_progress', nonce: wvbData.nonce, backup_id: backup_id },
                success: function (res) {
                    if (!res || !res.success) {
                        handleBackupError(res && res.data && res.data.message ? res.data.message : null);
                        return;
                    }
                    var data = res.data;
                    var pct  = data.progress || 0;
                    var step = data.step     || '';

                    updateProgress(pct, getStepLabel(step));

                    if (data.status === 'complete') {
                        $('.wvb-progress-bar').removeClass('animating');
                        updateProgress(100, 'بک‌آپ کامل شد');
                        showStatus(wvbData.strings.backup_complete, 'success');
                        enableButton();
                        return;
                    }
                    if (data.status === 'failed') {
                        handleBackupError(data.error || 'بک‌آپ با خطا متوقف شد');
                        return;
                    }
                    // Still running — poll again
                    pollProgress(backup_id, ticks + 1);
                },
                error: function (xhr) {
                    handleBackupError(extractErrorMsg(xhr));
                }
            });
        }, 4000); // poll every 4 seconds
    }

    function extractErrorMsg(xhr) {
        try {
            var parsed = JSON.parse(xhr.responseText);
            if (parsed && parsed.data && parsed.data.message) return parsed.data.message;
        } catch (e) {}
        if (xhr.responseText) {
            var tmp = document.createElement('div');
            tmp.innerHTML = xhr.responseText;
            var plain = (tmp.textContent || tmp.innerText || '').replace(/\s+/g, ' ').trim();
            if (plain.length > 0) return plain.substring(0, 400);
        }
        return null;
    }

    function getStepLabel(step) {
        switch (step) {
            case 'init':           return 'شروع...';
            case 'export_db':      return 'صادر کردن پایگاه داده...';
            case 'collect_files':  return 'جمع‌آوری فایل‌ها...';
            case 'chunk_files':    return 'فشرده‌سازی فایل‌ها...';
            case 'write_manifest': return 'نوشتن مانیفست...';
            case 'complete':       return 'بک‌آپ کامل شد';
            default:               return step;
        }
    }

    function updateProgress(pct, label) {
        $('.wvb-progress-bar').css('width', pct + '%');
        $('#backup-status-msg').text(label);
    }

    function handleBackupError(msg) {
        $('.wvb-progress-bar').removeClass('animating');
        showStatus(msg || wvbData.strings.backup_failed, 'error');
        enableButton();
    }

    function showStatus(msg, type) {
        var $s = $('#backup-status-msg');
        $s.show()
          .text(msg)
          .removeClass('wvb-notice-success wvb-notice-error')
          .addClass(type === 'success' ? 'wvb-notice-success' : 'wvb-notice-error');
    }

    function enableButton() {
        $('#start-backup-btn').prop('disabled', false).text('شروع بک‌آپ');
    }

    /* ------------------------------------------------------------------ */
    /* API Key                                                               */
    /* ------------------------------------------------------------------ */
    function initApiKey() {
        $('#copy-api-key').on('click', function () {
            var key = $('#api-key-full').text();
            navigator.clipboard.writeText(key).then(function () {
                var $btn = $('#copy-api-key');
                var orig = $btn.text();
                $btn.text(wvbData.strings.copied);
                setTimeout(function () {
                    $btn.text(orig);
                }, 2000);
            });
        });

        $('#regen-api-key').on('click', function () {
            if (!confirm(wvbData.strings.confirm_regen)) {
                return;
            }
            $.ajax({
                url: wvbData.rest_url + 'generate-key',
                method: 'POST',
                beforeSend: function (xhr) {
                    xhr.setRequestHeader('X-WP-Nonce', wvbData.rest_nonce);
                },
                success: function (res) {
                    alert('کلید جدید ایجاد شد: ' + res.api_key);
                    location.reload();
                },
                error: function () {
                    alert('خطا در بازتولید کلید');
                }
            });
        });
    }

    /* ------------------------------------------------------------------ */
    /* Schedule Times                                                        */
    /* ------------------------------------------------------------------ */
    function initScheduleTimes() {
        $('#add-time-btn').on('click', function () {
            var row = '<div class="wvb-schedule-row">' +
                '<input type="time" name="schedule_times[]" value="12:00" />' +
                '<button type="button" class="wvb-remove-time" title="حذف">&#215;</button>' +
                '</div>';
            $('#schedule-times-wrap').append(row);
        });

        $(document).on('click', '.wvb-remove-time', function () {
            if ($('.wvb-schedule-row').length <= 1) {
                alert('باید حداقل یک زمان وجود داشته باشد.');
                return;
            }
            $(this).closest('.wvb-schedule-row').remove();
        });
    }

    /* ------------------------------------------------------------------ */
    /* Delete Backup                                                         */
    /* ------------------------------------------------------------------ */
    function initDeleteBackup() {
        $(document).on('click', '.delete-backup-btn', function () {
            if (!confirm(wvbData.strings.confirm_delete)) {
                return;
            }
            var bid = $(this).data('backup-id');
            $.ajax({
                url: wvbData.rest_url + 'backups/' + bid,
                method: 'DELETE',
                beforeSend: function (xhr) {
                    xhr.setRequestHeader('X-API-Key', '');
                    xhr.setRequestHeader('X-WP-Nonce', wvbData.rest_nonce);
                },
                success: function () {
                    $(document).find('[data-backup-id="' + bid + '"]').closest('tr').fadeOut(400, function () {
                        $(this).remove();
                    });
                },
                error: function (xhr) {
                    alert('خطا در حذف بک‌آپ: ' + (xhr.responseJSON && xhr.responseJSON.message ? xhr.responseJSON.message : ''));
                }
            });
        });
    }

})(jQuery);
