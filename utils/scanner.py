from client_utils import log

from header import __id__
from utils.helpers import _ctrl, _invoke_sub_fragment_callback, _open_link_key, _run_on_plugins_queue, _setting_value_key, _shortcut_norm_text, _to_py_list


def _plugin_ids():
    try:
        ids = []
        for key in _ctrl().plugins.keySet().toArray():
            pid = str(key)
            if pid != __id__:
                ids.append(pid)
        ids.sort()
        return ids
    except Exception as e:
        log(f"[{__id__}] _plugin_ids: {e}")
        return []


def _get_item_type(it):
    if it is None:
        return ""
    if isinstance(it, dict):
        return str(it.get("type", "")).lower()
    t = getattr(it, "type", None)
    if isinstance(t, str):
        return t.lower()
    if callable(t):
        try:
            res = t()
            if isinstance(res, str):
                return res.lower()
        except Exception:
            pass
    cls_name = it.__class__.__name__.lower()
    if cls_name in ("switch", "selector", "input", "edittext", "edit_text", "text", "header", "divider", "button"):
        return "input" if "input" in cls_name or "edit" in cls_name else cls_name
    return str(t or "").lower()


def _get_item_key(it):
    if it is None:
        return None
    if isinstance(it, dict):
        return it.get("key") or it.get("setting_key")
    k = getattr(it, "key", None)
    if k is not None:
        return str(k)
    if hasattr(it, "getKey") and callable(it.getKey):
        try:
            return str(it.getKey())
        except Exception:
            pass
    return None


def _get_item_alias(it):
    if it is None:
        return None
    if isinstance(it, dict):
        return it.get("link_alias") or it.get("linkAlias") or it.get("alias")
    for attr in ("linkAlias", "link_alias", "alias", "getLinkAlias"):
        val = getattr(it, attr, None)
        if val is not None:
            if callable(val):
                try:
                    return str(val())
                except Exception:
                    continue
            return str(val)
    return None


def _get_item_text(it):
    if it is None:
        return ""
    if isinstance(it, dict):
        return str(it.get("text") or it.get("title") or it.get("hint") or it.get("subtext") or "")
    for attr in ("text", "title", "hint", "subtext", "getText", "getTitle"):
        val = getattr(it, attr, None)
        if val is not None:
            if callable(val):
                try:
                    res = val()
                    if res is not None:
                        return str(res)
                except Exception:
                    continue
            return str(val)
    return ""


def _get_item_cb(it):
    if it is None:
        return None
    if isinstance(it, dict):
        return it.get("create_sub_fragment") or it.get("createSubFragmentCallback") or it.get("createSubFragment")
    for attr in (
        "createSubFragmentCallback",
        "create_sub_fragment",
        "createSubFragment",
        "subFragmentCallback",
        "sub_fragment_callback",
        "getCreateSubFragmentCallback",
    ):
        val = getattr(it, attr, None)
        if val is not None:
            return val
    return None


def _get_item_click_cb(it):
    if it is None:
        return None
    if isinstance(it, dict):
        return it.get("on_click") or it.get("onClickCallback") or it.get("onClick")
    for attr in ("on_click", "onClickCallback", "onClick", "on_long_click", "onLongClickCallback"):
        val = getattr(it, attr, None)
        if val is not None:
            return val
    return None


def _invoke_click_callback(cb):
    if cb is None:
        return
    if callable(cb):
        try:
            cb()
            return
        except TypeError:
            try:
                cb(None)
                return
            except Exception:
                pass
        except Exception:
            pass
    for method in ("call", "run", "onClick", "on_click", "invoke"):
        if hasattr(cb, method):
            try:
                fn = getattr(cb, method)
                try:
                    fn()
                    return
                except TypeError:
                    fn(None)
                    return
            except Exception:
                pass


def _get_item_items(it):
    if it is None:
        return []
    if isinstance(it, dict):
        return it.get("items") or it.get("options") or []
    for attr in ("items", "options", "getItems", "getOptions"):
        val = getattr(it, attr, None)
        if val is not None:
            if callable(val):
                try:
                    res = val()
                    if res is not None:
                        return _to_py_list(res)
                except Exception:
                    continue
            return _to_py_list(val)
    return []


def _has_settings(pid):
    ctrl = _ctrl()
    try:
        p = ctrl.plugins.get(pid)
        if p is not None:
            for method_name in ("create_settings", "createSettings", "get_settings_list", "getSettingsList"):
                if hasattr(p, method_name):
                    return True
    except Exception:
        pass
    try:
        if ctrl.hasPluginSettings(pid):
            return True
        lst = ctrl.getPluginSettingsList(pid)
        if lst is not None:
            return True
    except Exception:
        pass
    return False


def _get_settings_list(pid, ensure_loaded=False):
    ctrl = _ctrl()
    # 1. Direct Python plugin instance
    try:
        p = ctrl.plugins.get(pid)
        if p is not None:
            for method_name in ("create_settings", "createSettings", "get_settings_list", "getSettingsList"):
                if hasattr(p, method_name):
                    fn = getattr(p, method_name)
                    if callable(fn):
                        try:
                            res = fn()
                            if res is not None:
                                return res
                        except Exception as e:
                            log(f"[{__id__}] direct {method_name} {pid}: {e}")
    except Exception as e:
        log(f"[{__id__}] direct plugin get {pid}: {e}")

    # 2. Controller cached list
    try:
        lst = ctrl.getPluginSettingsList(pid)
        if lst is not None:
            return lst
    except Exception:
        pass

    # 3. Load via controller if requested
    if ensure_loaded:
        try:
            ctrl.loadPluginSettings(pid)
            lst = ctrl.getPluginSettingsList(pid)
            if lst is not None:
                return lst
        except Exception:
            pass

    return None


def _has_settings_reliably(pid):
    return _has_settings(pid)


def _collect_sub_fragments(pid, ensure_loaded=True):
    out = []
    if pid == __id__:
        return out

    try:
        lst = _get_settings_list(pid, ensure_loaded=ensure_loaded)
    except Exception:
        lst = None
    if not lst:
        return out

    def _join_label(parent_label, current_text):
        p = str(parent_label or "").strip()
        c = str(current_text or "").strip()
        if p and c:
            return f"{p} / {c}"
        return c or p

    visited_paths = set()
    max_depth = 6

    def _walk(definitions, pf, parent_label, depth):
        if definitions is None or depth > max_depth:
            return
        for idx, it in enumerate(_to_py_list(definitions)):
            try:
                cb = _get_item_cb(it)
                if not cb:
                    continue
                key = _get_item_key(it)
                alias = _get_item_alias(it)
                raw_text = _get_item_text(it) or str(key or "")
                text = _join_label(parent_label, raw_text)
                branch = alias or key or f"sub_{depth}_{idx}_{_shortcut_norm_text(raw_text or '') or 'item'}"
                subprefix = branch if not pf else f"{pf}:{branch}"
                if subprefix in visited_paths:
                    continue
                visited_paths.add(subprefix)
                out.append({"key": subprefix, "text": text, "alias": alias})
                try:
                    py = _invoke_sub_fragment_callback(cb)
                    if py is not None:
                        _walk(py, subprefix, text, depth + 1)
                except Exception as e:
                    log(f"[{__id__}] _collect_sub_fragments sub-walk: {e}")
            except Exception as e:
                log(f"[{__id__}] _collect_sub_fragments item parse: {e}")

    try:
        _walk(lst, "", "", 0)
    except Exception as e:
        log(f"[{__id__}] _collect_sub_fragments walk: {e}")
    return out


def _collect_settings(pid, prefix=None, ensure_loaded=True):
    out = []
    if pid == __id__:
        return out

    try:
        lst = _get_settings_list(pid, ensure_loaded=ensure_loaded)
    except Exception:
        lst = None
    if not lst:
        return out

    def _add(t, key, text, items=None, pf=None, alias=None):
        kp = f"{pf}:{key}" if pf else key
        out.append({"type": t, "key": kp, "value_key": key, "open_key": _open_link_key(pf, key, alias), "text": text, "items": [str(x) for x in (items or [])]})

    def _join_label(parent_label, current_text):
        p = str(parent_label or "").strip()
        c = str(current_text or "").strip()
        if p and c:
            return f"{p} / {c}"
        return c or p

    visited_paths = set()
    max_depth = 6

    def _walk(definitions, pf, parent_label, depth):
        if definitions is None or depth > max_depth:
            return
        for idx, it in enumerate(_to_py_list(definitions)):
            try:
                itype = _get_item_type(it)
                key = _get_item_key(it)
                alias = _get_item_alias(it)
                raw_text = _get_item_text(it) or str(key or "")
                text = _join_label(parent_label, raw_text)
                click_cb = _get_item_click_cb(it)

                if key and (
                    itype in ("switch", "selector", "input", "edit_text", "edittext") or itype not in ("text", "header", "divider", "button", "action")
                ):
                    if itype == "selector":
                        opts = _get_item_items(it)
                        _add("selector", key, text, opts, pf=pf, alias=alias)
                    elif itype == "switch":
                        _add("switch", key, text, pf=pf, alias=alias)
                    else:
                        _add("input", key, text, pf=pf, alias=alias)
                    continue

                if click_cb is not None or itype in ("button", "action"):
                    item_key = key or alias or f"btn_{depth}_{idx}_{_shortcut_norm_text(raw_text or '') or 'item'}"
                    _add("button", item_key, text, pf=pf, alias=alias)
                    continue

                cb = _get_item_cb(it)
                if not cb:
                    continue
                branch = alias or key or f"wizard_{depth}_{idx}_{_shortcut_norm_text(raw_text or '') or 'item'}"
                subprefix = branch if not pf else f"{pf}:{branch}"
                if subprefix in visited_paths:
                    continue
                visited_paths.add(subprefix)
                py = _invoke_sub_fragment_callback(cb)
                if py is not None:
                    _walk(py, subprefix, text, depth + 1)
            except Exception as e:
                log(f"[{__id__}] _collect_settings item parse: {e}")

    try:
        _walk(lst, prefix, "", 0)
    except Exception as e:
        log(f"[{__id__}] _collect_settings walk: {e}")
    return out


def _find_setting_item(pid, sc):
    target_full = str(sc.get("setting_key", "") or "")
    target_open = str(sc.get("setting_open_key", target_full) or "")
    target_value = _setting_value_key(sc)
    visited_paths = set()

    def _walk(definitions, pf, depth):
        if definitions is None or depth > 6:
            return None
        for idx, it in enumerate(_to_py_list(definitions)):
            try:
                key = _get_item_key(it)
                alias = _get_item_alias(it)
                click_cb = _get_item_click_cb(it)
                itype = _get_item_type(it)
                raw_text = _get_item_text(it) or str(key or "")

                is_btn = click_cb is not None or itype in ("button", "action")
                btn_fallback = alias or f"btn_{depth}_{idx}_{_shortcut_norm_text(raw_text or '') or 'item'}"
                item_key = key or (btn_fallback if is_btn else None)
                if item_key:
                    kp = f"{pf}:{item_key}" if pf else str(item_key)
                    op = _open_link_key(pf, str(item_key), alias)
                    alias_match = bool(alias and (alias == target_value or alias == target_full))
                    if kp == target_full or op == target_open or (not pf and str(item_key) == target_value) or alias_match:
                        return it

                cb = _get_item_cb(it)
                if not cb:
                    continue
                branch = alias or key or f"wizard_{depth}_{idx}_{_shortcut_norm_text(raw_text or '') or 'item'}"
                subprefix = str(branch) if not pf else f"{pf}:{branch}"
                if subprefix in visited_paths:
                    continue
                visited_paths.add(subprefix)
                py = _invoke_sub_fragment_callback(cb)
                if py is not None:
                    found = _walk(py, subprefix, depth + 1)
                    if found:
                        return found
            except Exception as e:
                log(f"[{__id__}] find setting item: {e}")
        return None

    try:
        return _walk(_get_settings_list(pid, ensure_loaded=False), "", 0)
    except Exception as e:
        log(f"[{__id__}] find setting item root: {e}")
        return None


def _trigger_setting_on_change(pid, sc, value):
    try:
        item = _find_setting_item(pid, sc)
        cb = getattr(item, "onChangeCallback", getattr(item, "on_change", getattr(item, "onChange", None)))
        if not cb:
            return

        def _call():
            try:
                if callable(cb):
                    cb(value)
                elif hasattr(cb, "call"):
                    cb.call(value)
            except Exception as e:
                log(f"[{__id__}] on_change callback {pid}:{_setting_value_key(sc)}: {e}")

        _run_on_plugins_queue(_call)
    except Exception as e:
        log(f"[{__id__}] trigger on_change: {e}")


def _find_sub_fragment_item(pid, sub_key):
    visited_paths = set()
    max_depth = 6

    def _walk(definitions, pf, depth):
        if definitions is None or depth > max_depth:
            return None
        for idx, it in enumerate(_to_py_list(definitions)):
            try:
                cb = _get_item_cb(it)
                if not cb:
                    continue
                key = _get_item_key(it)
                alias = _get_item_alias(it)
                raw_text = _get_item_text(it) or str(key or "")
                branch = alias or key or f"sub_{depth}_{idx}_{_shortcut_norm_text(raw_text or '') or 'item'}"
                subprefix = branch if not pf else f"{pf}:{branch}"

                if subprefix == sub_key or (alias and alias == sub_key):
                    return it

                if subprefix in visited_paths:
                    continue
                visited_paths.add(subprefix)
                py = _invoke_sub_fragment_callback(cb)
                if py is not None:
                    res = _walk(py, subprefix, depth + 1)
                    if res:
                        return res
            except Exception:
                pass
        return None

    try:
        return _walk(_get_settings_list(pid, ensure_loaded=False), "", 0)
    except Exception:
        return None
