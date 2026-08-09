import json
import urllib.parse

from android_utils import run_on_ui_thread
from base_plugin import MethodHook
from client_utils import log
from java import dynamic_proxy, jclass
from org.telegram.messenger import AndroidUtilities
from ui.bulletin import BulletinHelper

from header import __id__
from i18n.locales import _s
from utils.helpers import _ctrl, _dialog_context, _loc_label, _plugin_exists, _plugin_name, _sc_label, _show_dialog_safe


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


def _is_shortcut_url(url_str):
    if not url_str:
        return False
    u = str(url_str).strip().lower()
    return u.startswith("tg://shortcuts?") or u == "tg://shortcuts"


def _on_open_url_before(plugin, param):
    try:
        if not param.args or len(param.args) < 2:
            return
        raw = param.args[1]
        url_str = str(raw) if raw else ""
        if _is_shortcut_url(url_str):
            param.setResult(None)
            _handle_deeplink(plugin, url_str)
    except Exception as e:
        log(f"[{__id__}] _on_open_url_before: {e}")


def _handle_deeplink(plugin, url_str):
    def _do():
        try:
            Uri = jclass("android.net.Uri")
            parsed_url = url_str if "://" in url_str else f"https://{url_str}"
            uri = Uri.parse(parsed_url)

            pid = str(uri.getQueryParameter("plugin_id") or "").strip()
            if not pid:
                run_on_ui_thread(lambda: BulletinHelper.show_error(_s("invalid_deeplink")))
                return

            stype = str(uri.getQueryParameter("type") or "toggle_plugin").strip()
            if stype not in ("toggle_plugin", "open_settings", "operate_setting"):
                stype = "toggle_plugin"

            label = str(uri.getQueryParameter("label") or "").strip()
            icon = str(uri.getQueryParameter("icon") or "media_settings").strip()
            locations_param = str(uri.getQueryParameter("locations") or "").strip()
            loc = str(uri.getQueryParameter("location") or "drawer").strip()
            locations = [item.strip() for item in locations_param.split(",") if item.strip()] if locations_param else None

            sc = {
                "type": stype,
                "plugin_id": pid,
                "location": loc if loc in ("drawer", "chat", "message", "profile", "both") else "drawer",
                "label": label,
                "icon": icon if icon else "media_settings",
            }
            if locations:
                valid_locations = [loc_item for loc_item in locations if loc_item in ("drawer", "chat", "message", "profile")]
                if valid_locations:
                    sc["locations"] = valid_locations

            if stype == "open_settings":
                sub_fragment = str(uri.getQueryParameter("sub_fragment") or "").strip()
                if sub_fragment and sub_fragment != "root":
                    sc["sub_fragment"] = sub_fragment

            elif stype == "operate_setting":
                setting_key = str(uri.getQueryParameter("setting_key") or "").strip()
                if setting_key:
                    sc["setting_key"] = setting_key
                setting_value_key = str(uri.getQueryParameter("setting_value_key") or "").strip()
                if setting_value_key:
                    sc["setting_value_key"] = setting_value_key
                elif setting_key:
                    sc["setting_value_key"] = setting_key

                setting_open_key = str(uri.getQueryParameter("setting_open_key") or "").strip()
                if setting_open_key:
                    sc["setting_open_key"] = setting_open_key
                elif setting_key:
                    sc["setting_open_key"] = setting_key

                setting_type = str(uri.getQueryParameter("setting_type") or "switch").strip()
                sc["setting_type"] = setting_type if setting_type in ("switch", "selector", "input") else "switch"

                raw_items = uri.getQueryParameter("setting_items")
                if raw_items:
                    try:
                        parsed_items = json.loads(str(raw_items))
                        if isinstance(parsed_items, list):
                            sc["setting_items"] = [str(x) for x in parsed_items]
                    except Exception:
                        sc["setting_items"] = [x.strip() for x in str(raw_items).split(",") if x.strip()]

            frag, context = _dialog_context()
            if not context:
                return

            sc_list = plugin._load_shortcuts()
            existing_idx = None
            for i, existing in enumerate(sc_list):
                if (
                    existing.get("plugin_id") == pid
                    and existing.get("type") == stype
                    and existing.get("sub_fragment", "") == sc.get("sub_fragment", "")
                    and existing.get("setting_key", "") == sc.get("setting_key", "")
                ):
                    existing_idx = i
                    break

            plugin_installed = _plugin_exists(pid)
            pname = _plugin_name(pid)
            dis_label = label or _sc_label(sc)

            type_descriptions = {
                "toggle_plugin": _s("toggle_plugin"),
                "open_settings": _s("open_settings"),
                "operate_setting": _s("operate_setting"),
            }
            type_text = type_descriptions.get(stype, _s("toggle_plugin"))

            msg_lines = [
                _s("add_deeplink_confirm"),
                "",
                f"{_s('custom_label')}: {dis_label}",
                f"{_s('plugins')}: {pname} [{pid}]",
                f"{_s('type')}: {type_text}",
                f"{_s('location')}: {_loc_label(sc)}",
            ]
            if not plugin_installed:
                msg_lines.extend(["", f"⚠️ {_s('plugin_not_installed')}"])
            elif existing_idx is not None:
                msg_lines.extend(["", f"ℹ️ {_s('shortcut_exists')}"])

            message_text = "\n".join(msg_lines)

            AlertDialog = jclass("org.telegram.ui.ActionBar.AlertDialog")
            builder = AlertDialog.Builder(context)
            builder.setTitle(_s("add_shortcut"))
            builder.setMessage(message_text)

            OnButtonClickListener = dynamic_proxy(jclass("org.telegram.ui.ActionBar.AlertDialog$OnButtonClickListener"))

            class AddClick(OnButtonClickListener):
                def onClick(self, dialog, which):
                    shortcuts = plugin._load_shortcuts()
                    if existing_idx is not None and 0 <= existing_idx < len(shortcuts):
                        shortcuts[existing_idx] = sc
                        msg_key = "shortcut_updated"
                    else:
                        shortcuts.append(sc)
                        msg_key = "shortcut_created"
                    plugin._save_shortcuts(shortcuts)
                    plugin._restore_shortcuts()
                    run_on_ui_thread(lambda: BulletinHelper.show_success(f"{_s(msg_key)}: {dis_label}"))
                    try:
                        _ctrl().loadPluginSettings(__id__)
                    except Exception:
                        pass

            class RunClick(OnButtonClickListener):
                def onClick(self, dialog, which):
                    try:
                        plugin._exec_shortcut(sc)
                    except Exception as e:
                        log(f"[{__id__}] run from deeplink error: {e}")

            action_btn_text = _s("update") if existing_idx is not None else _s("create")
            builder.setPositiveButton(action_btn_text, AddClick())
            if plugin_installed:
                builder.setNeutralButton(_s("run_now"), RunClick())
            builder.setNegativeButton(_s("cancel"), None)

            dialog = builder.create()
            _show_dialog_safe(frag, dialog)
        except Exception as e:
            log(f"[{__id__}] handle_deeplink error: {e}")
            err_msg = str(e)
            run_on_ui_thread(lambda: BulletinHelper.show_error(err_msg))

    run_on_ui_thread(_do)


def _generate_deeplink(plugin, sc):
    try:
        stype = str(sc.get("type") or "toggle_plugin")
        pid = str(sc.get("plugin_id") or "")
        lbl = str(sc.get("label") or "")
        ic = str(sc.get("icon") or "media_settings")
        loc = str(sc.get("location") or "drawer")

        params = {
            "type": stype,
            "plugin_id": pid,
            "label": lbl,
            "icon": ic,
            "location": loc,
        }

        raw_locations = sc.get("locations")
        if isinstance(raw_locations, (list, tuple)):
            loc_str = ",".join(str(x) for x in raw_locations if x)
            if loc_str:
                params["locations"] = loc_str

        if stype == "open_settings":
            sub = str(sc.get("sub_fragment") or "")
            if sub and sub != "root":
                params["sub_fragment"] = sub

        elif stype == "operate_setting":
            sk = str(sc.get("setting_key") or "")
            if sk:
                params["setting_key"] = sk
            svk = str(sc.get("setting_value_key") or "")
            if svk and svk != sk:
                params["setting_value_key"] = svk
            sok = str(sc.get("setting_open_key") or "")
            if sok and sok != sk:
                params["setting_open_key"] = sok
            st = str(sc.get("setting_type") or "switch")
            if st:
                params["setting_type"] = st
            items = sc.get("setting_items") or sc.get("items")
            if isinstance(items, (list, tuple)) and items:
                params["setting_items"] = json.dumps([str(x) for x in items], ensure_ascii=False)

        query_str = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        return f"tg://shortcuts?{query_str}"
    except Exception as e:
        log(f"[{__id__}] _generate_deeplink: {e}")
        return ""


def copy_deeplink(plugin, sc):
    try:
        link = _generate_deeplink(plugin, sc)
        if not link:
            run_on_ui_thread(lambda: BulletinHelper.show_error(_s("error")))
            return

        AndroidUtilities.addToClipboard(link)
        msg = _s("deeplink_copied")
        run_on_ui_thread(lambda: BulletinHelper.show_success(msg))
    except Exception as e:
        log(f"[{__id__}] copy_deeplink error: {e}")
        err_msg = str(e)
        run_on_ui_thread(lambda: BulletinHelper.show_error(err_msg))
