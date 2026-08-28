import traceback

from android_utils import run_on_ui_thread
from client_utils import log
from java import dynamic_proxy, jclass

from features.deeplink import copy_deeplink
from header import __id__
from i18n.locales import _s
from ui.settings import Divider, Text
from ui.wizard import build_new_wizard, build_wizard_step1
from utils.helpers import (
    _ctrl,
    _dialog_context,
    _plugin_name,
    _sc_label,
    _show_bulletin_error,
    _show_bulletin_success,
    _show_dialog_safe,
)
from utils.scanner import _trigger_setting_on_change


def build_settings_list(plugin):
    settings = []

    shortcuts = plugin._load_shortcuts()
    for i, sc in enumerate(shortcuts):
        label = _sc_label(sc)
        pid = sc.get("plugin_id", "")
        if sc.get("is_system"):
            settings.append(
                Text(
                    text=label,
                    icon=sc.get("icon") or "media_settings",
                    create_sub_fragment=build_wizard_step1(plugin, edit_index=i),
                )
            )
            settings.append(Divider())
        else:
            display_text = f"{label} [{pid}]" if pid else label
            settings.append(
                Text(
                    text=display_text,
                    icon=sc.get("icon") or "media_settings",
                    create_sub_fragment=lambda _i=i, _sc=sc: build_shortcut_actions(plugin, _i, _sc),
                )
            )
    settings.append(Text(text=_s("add_shortcut"), accent=True, create_sub_fragment=build_new_wizard(plugin)))

    return settings


def _get_current_shortcut(plugin, index, fallback_sc=None):
    try:
        shortcuts = plugin._load_shortcuts()
        if 0 <= index < len(shortcuts):
            return shortcuts[index]
    except Exception:
        pass
    return fallback_sc or {}


def build_shortcut_actions(plugin, index, initial_sc=None):
    def _do_exec(_value):
        sc = _get_current_shortcut(plugin, index, initial_sc)
        plugin._exec_shortcut(sc)

    def _do_copy(_value):
        sc = _get_current_shortcut(plugin, index, initial_sc)
        copy_deeplink(plugin, sc)

    actions = [
        Text(text=_s("open_shortcut"), icon="msg_share", on_click=_do_exec),
        Text(
            text=_s("edit_shortcut"),
            icon="msg_edit",
            create_sub_fragment=build_wizard_step1(plugin, edit_index=index),
        ),
        Text(text=_s("copy_deeplink"), icon="msg_copy", on_click=_do_copy),
    ]
    curr_sc = _get_current_shortcut(plugin, index, initial_sc)
    if not curr_sc.get("is_system"):
        actions.append(Text(text=_s("remove_shortcut"), icon="msg_delete", red=True, on_click=lambda _value: plugin._remove_shortcut(index)))
    return actions


def show_selector_dialog(plugin, pid, key, title, items, sc=None):
    def _do():
        try:
            opts = [str(x) for x in (items or [])]
            if not opts:
                plugin._open_settings_or_subfragment(pid)
                return
            frag, context = _dialog_context()
            if not context:
                return
            try:
                cur = _ctrl().getPluginSettingInt(pid, key, 0)
            except Exception:
                cur = 0

            AlertDialog = jclass("org.telegram.ui.ActionBar.AlertDialog")
            LinearLayout = jclass("android.widget.LinearLayout")
            RadioColorCell = jclass("org.telegram.ui.Cells.RadioColorCell")
            Theme = jclass("org.telegram.ui.ActionBar.Theme")
            AndroidUtilities = jclass("org.telegram.messenger.AndroidUtilities")
            OnClick = dynamic_proxy(jclass("android.view.View$OnClickListener"))

            layout = LinearLayout(context)
            layout.setOrientation(1)
            dialog_ref = [None]

            def make_click(idx):
                class CellClick(OnClick):
                    def onClick(self, view):
                        try:
                            if dialog_ref[0]:
                                dialog_ref[0].dismiss()
                            value = int(idx)
                            _ctrl().setPluginSetting(pid, key, value)
                            if sc:
                                _trigger_setting_on_change(pid, sc, value)
                            _show_bulletin_success(f"{_plugin_name(pid)}: {opts[idx]}")
                        except Exception as e:
                            log(f"[{__id__}] selector dialog save: {e}")

                return CellClick()

            for i, opt in enumerate(opts):
                cell = RadioColorCell(context)
                try:
                    cell.setPadding(AndroidUtilities.dp(4.0), 0, AndroidUtilities.dp(4.0), 0)
                except Exception:
                    pass
                try:
                    cell.setCheckColor(Theme.getColor(Theme.key_radioBackground), Theme.getColor(Theme.key_dialogRadioBackgroundChecked))
                except Exception:
                    pass
                cell.setTextAndValue(opt, int(cur) == i)
                try:
                    cell.setBackground(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2))
                except Exception:
                    pass
                cell.setOnClickListener(make_click(i))
                layout.addView(cell)

            builder = AlertDialog.Builder(context)
            builder.setTitle(title or _s("choose_value"))
            builder.setView(layout)
            builder.setNegativeButton(_s("cancel"), None)
            dialog_ref[0] = builder.create()
            _show_dialog_safe(frag, dialog_ref[0])
        except Exception as e:
            log(f"[{__id__}] show selector dialog: {e}\n{traceback.format_exc()}")
            _show_bulletin_error(str(e))

    run_on_ui_thread(_do)


def show_input_dialog(plugin, pid, key, title, sc=None):
    def _do():
        try:
            frag, context = _dialog_context()
            if not context:
                return

            try:
                cur = str(_ctrl().getPluginSettingString(pid, key, "") or "")
            except Exception:
                cur = ""

            AlertDialog = jclass("org.telegram.ui.ActionBar.AlertDialog")
            EditTextBoldCursor = jclass("org.telegram.ui.Components.EditTextBoldCursor")
            FrameLayout = jclass("android.widget.FrameLayout")
            Theme = jclass("org.telegram.ui.ActionBar.Theme")
            AndroidUtilities = jclass("org.telegram.messenger.AndroidUtilities")
            OnButtonClick = dynamic_proxy(jclass("android.content.DialogInterface$OnClickListener"))
            OnShow = dynamic_proxy(jclass("android.content.DialogInterface$OnShowListener"))
            OnDismiss = dynamic_proxy(jclass("android.content.DialogInterface$OnDismissListener"))

            layout = FrameLayout(context)
            try:
                layout.setPadding(AndroidUtilities.dp(24.0), AndroidUtilities.dp(8.0), AndroidUtilities.dp(24.0), AndroidUtilities.dp(8.0))
            except Exception:
                pass

            edit = EditTextBoldCursor(context)
            edit.setText(cur)
            edit.setTextSize(1, 16.0)
            try:
                edit.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
                edit.setHintColor(Theme.getColor(Theme.key_dialogTextHint))
                edit.setCursorColor(Theme.getColor(Theme.key_dialogFloatingButton))
                edit.setCursorSize(AndroidUtilities.dp(20.0))
                edit.setCursorWidth(1.5)
            except Exception:
                pass
            layout.addView(edit)

            class SaveClick(OnButtonClick):
                def onClick(self, dialog, which):
                    try:
                        value = edit.getText().toString()
                        _ctrl().setPluginSetting(pid, key, value)
                        if sc:
                            _trigger_setting_on_change(pid, sc, value)
                        _show_bulletin_success(f"{_plugin_name(pid)}: {value}")
                    except Exception as e:
                        log(f"[{__id__}] input dialog save: {e}")

            builder = AlertDialog.Builder(context)
            builder.setTitle(title or _s("text_value"))
            try:
                builder.makeCustomMaxHeight()
            except Exception:
                pass
            builder.setView(layout)
            try:
                builder.setWidth(AndroidUtilities.dp(292.0))
            except Exception:
                pass
            builder.setPositiveButton(_s("save"), SaveClick())
            builder.setNegativeButton(_s("cancel"), None)

            class ShowKeyboard(OnShow):
                def onShow(self, dialog):
                    try:
                        edit.requestFocus()
                        edit.setSelection(edit.length())
                        AndroidUtilities.showKeyboard(edit)
                    except Exception:
                        pass

            class HideKeyboard(OnDismiss):
                def onDismiss(self, dialog):
                    try:
                        AndroidUtilities.hideKeyboard(edit)
                    except Exception:
                        pass

            dialog = builder.create()
            try:
                dialog.setOnShowListener(ShowKeyboard())
                dialog.setOnDismissListener(HideKeyboard())
            except Exception:
                pass
            _show_dialog_safe(frag, dialog)
        except Exception as e:
            log(f"[{__id__}] show input dialog: {e}\n{traceback.format_exc()}")
            _show_bulletin_error(str(e))

    run_on_ui_thread(_do)
