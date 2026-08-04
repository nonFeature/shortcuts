import urllib.parse

from android_utils import run_on_ui_thread
from base_plugin import MethodHook
from client_utils import log
from java import dynamic_proxy, jclass
from org.telegram.messenger import AndroidUtilities
from ui.bulletin import BulletinHelper

from header import __id__
from i18n.locales import _s
from utils.helpers import _dialog_context, _loc_label, _plugin_name, _sc_label, _show_dialog_safe


def register_deeplink_hook(plugin):
    try:
        BrowserClass = jclass("org.telegram.messenger.browser.Browser")
        return plugin.hook_all_methods(BrowserClass, "openUrl", _OpenUrlHook(plugin))
    except Exception as e:
        log(f"[{__id__}] _register_deeplink_hook error: {e}")
        return None


class _OpenUrlHook(MethodHook):
    def __init__(self, plugin):
        self.plugin = plugin

    def before_hooked_method(self, param):
        _on_open_url_before(self.plugin, param)


def _on_open_url_before(plugin, param):
    try:
        if not param.args or len(param.args) < 2:
            return
        raw = param.args[1]
        url_str = str(raw) if raw else ""
        if url_str.startswith("tg://shortcut") or url_str.startswith("https://t.me/shortcut"):
            param.setResult(None)
            _handle_deeplink(plugin, url_str)
    except Exception as e:
        log(f"[{__id__}] _on_open_url_before: {e}")


def _handle_deeplink(plugin, url_str):
    def _do():
        try:
            Uri = jclass("android.net.Uri")
            uri = Uri.parse(url_str)
            stype = str(uri.getQueryParameter("type") or "open_settings")
            pid = str(uri.getQueryParameter("plugin_id") or "")
            setting_key = str(uri.getQueryParameter("setting_key") or "")
            sub_fragment = str(uri.getQueryParameter("sub_fragment") or "")
            label = str(uri.getQueryParameter("label") or "")
            icon = str(uri.getQueryParameter("icon") or "media_settings")
            loc = str(uri.getQueryParameter("location") or "drawer")

            sc = {"type": stype, "plugin_id": pid, "location": loc, "label": label, "icon": icon, "setting_key": setting_key, "sub_fragment": sub_fragment}

            frag, context = _dialog_context()
            if not context:
                return

            AlertDialog = jclass("org.telegram.ui.ActionBar.AlertDialog")
            builder = AlertDialog.Builder(context)
            builder.setTitle(_s("add_shortcut"))
            dis_label = label or _sc_label(sc)
            builder.setMessage(
                f"{_s('add_deeplink_confirm')}\n\n{_s('custom_label')}: {dis_label}\n{_s('plugins')}: {_plugin_name(pid)}\n{_s('location')}: {_loc_label(loc)}"
            )

            class AddClick(dynamic_proxy(jclass("org.telegram.ui.ActionBar.AlertDialog$OnButtonClickListener"))):
                def onClick(self, dialog, which):
                    sc_list = plugin._load_shortcuts()
                    sc_list.append(sc)
                    plugin._save_shortcuts(sc_list)
                    plugin._restore_shortcuts()
                    run_on_ui_thread(lambda: BulletinHelper.show_info(f"{_s('shortcut_created')}: {dis_label}"))

            builder.setPositiveButton(_s("create"), AddClick())
            builder.setNegativeButton(_s("cancel"), None)
            dialog = builder.create()
            _show_dialog_safe(frag, dialog)
        except Exception as e:
            log(f"[{__id__}] handle_deeplink error: {e}")

    run_on_ui_thread(_do)


def _generate_deeplink(plugin, sc):
    try:
        stype = sc.get("type", "toggle_plugin")
        pid = sc.get("plugin_id", "")
        sk = sc.get("setting_key", "")
        sub = sc.get("sub_fragment", "")
        lbl = sc.get("label", "")
        ic = sc.get("icon", "media_settings")
        loc = sc.get("location", "drawer")
        link = f"tg://shortcut?type={urllib.parse.quote(stype)}&plugin_id={urllib.parse.quote(pid)}&setting_key={urllib.parse.quote(sk)}&sub_fragment={urllib.parse.quote(sub)}&label={urllib.parse.quote(lbl)}&icon={urllib.parse.quote(ic)}&location={urllib.parse.quote(loc)}"
        return link
    except Exception as e:
        log(f"[{__id__}] _generate_deeplink: {e}")
        return ""


def copy_deeplink(plugin, sc):
    link = _generate_deeplink(plugin, sc)
    if link:
        run_on_ui_thread(lambda: (AndroidUtilities.addToClipboard(link), BulletinHelper.show_info(_s("deeplink_copied"))))
