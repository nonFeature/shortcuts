import time
from client_utils import log
from com.exteragram.messenger.plugins import PluginsController

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

def _has_settings(pid):
    try:
        ctrl = _ctrl()
        if ctrl.hasPluginSettings(pid):
            return True
        lst = ctrl.getPluginSettingsList(pid)
        if lst is not None:
            return True
        if ctrl.hasPluginSettingsPreferences(pid):
            return True
    except:
        pass
    return False

def _get_settings_list(pid, ensure_loaded=False, wait_seconds=0.6):
    ctrl = _ctrl()
    try:
        lst = ctrl.getPluginSettingsList(pid)
        if lst is not None:
            return lst
    except:
        pass
    if not ensure_loaded:
        return None
    try:
        ctrl.loadPluginSettings(pid)
    except:
        return None
    deadline = time.time() + max(0.0, float(wait_seconds))
    while time.time() < deadline:
        try:
            lst = ctrl.getPluginSettingsList(pid)
            if lst is not None:
                return lst
        except:
            pass
        time.sleep(0.05)
    try:
        return ctrl.getPluginSettingsList(pid)
    except:
        return None

def _has_settings_reliably(pid):
    if _has_settings(pid):
        return True
    lst = _get_settings_list(pid, ensure_loaded=True, wait_seconds=0.45)
    return lst is not None

def _collect_sub_fragments(pid):
    out = []
    try:
        lst = _get_settings_list(pid, ensure_loaded=True)
    except:
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
                itype = getattr(it, "type", None)
                if itype != "text":
                    continue
                cb = getattr(it, "createSubFragmentCallback", None)
                if not cb:
                    continue
                key = getattr(it, "key", None)
                alias = getattr(it, "linkAlias", None)
                raw_text = getattr(it, "text", getattr(it, "hint", str(key or "")))
                text = _join_label(parent_label, raw_text)
                branch = alias or key or f"sub_{depth}_{idx}_{_shortcut_norm_text(raw_text or '') or 'item'}"
                subprefix = branch if not pf else f"{pf}:{branch}"
                if subprefix in visited_paths:
                    continue
                visited_paths.add(subprefix)
                out.append({
                    "key": subprefix,
                    "text": text,
                    "alias": alias
                })
                try:
                    py = _invoke_sub_fragment_callback(cb)
                    nested_src = py.asList() if hasattr(py, "asList") else py
                    eng = PluginsController.engines.get("python")
                    nested = None
                    if eng:
                        try:
                            nested = eng.parsePySettingDefinitions(nested_src)
                        except:
                            nested = None
                    if nested is None:
                        nested = nested_src
                    _walk(nested, subprefix, text, depth + 1)
                except Exception as e:
                    log(f"[{__id__}] _collect_sub_fragments sub-walk: {e}")
            except Exception as e:
                log(f"[{__id__}] _collect_sub_fragments item parse: {e}")

    try:
        _walk(lst, "", "", 0)
    except Exception as e:
        log(f"[{__id__}] _collect_sub_fragments walk: {e}")
    return out

def _collect_settings(pid, prefix=None):
    out = []
    try:
        lst = _get_settings_list(pid, ensure_loaded=True)
    except:
        lst = None
    if not lst:
        return out

    def _add(t, key, text, items=None, pf=None, alias=None):
        kp = f"{pf}:{key}" if pf else key
        out.append({
            "type": t,
            "key": kp,
            "value_key": key,
            "open_key": _open_link_key(pf, key, alias),
            "text": text,
            "items": [str(x) for x in (items or [])]
        })

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
                itype = getattr(it, "type", None)
                key = getattr(it, "key", None)
                alias = getattr(it, "linkAlias", None)
                raw_text = getattr(it, "text", getattr(it, "hint", str(key)))
                text = _join_label(parent_label, raw_text)
                if itype in ("switch", "selector", "input", "edit_text"):
                    if not key:
                        continue
                    if itype == "selector":
                        opts = _to_py_list(getattr(it, "items", None))
                        _add("selector", key, text, opts, pf=pf, alias=alias)
                    elif itype == "switch":
                        _add("switch", key, text, pf=pf, alias=alias)
                    else:
                        _add("input", key, text, pf=pf, alias=alias)
                    continue
                if itype != "text":
                    continue
                cb = getattr(it, "createSubFragmentCallback", None)
                if not cb:
                    continue
                branch = alias or key or f"wizard_{depth}_{idx}_{_shortcut_norm_text(raw_text or '') or 'item'}"
                subprefix = branch if not pf else f"{pf}:{branch}"
                if subprefix in visited_paths:
                    continue
                visited_paths.add(subprefix)
                py = _invoke_sub_fragment_callback(cb)
                nested_src = py.asList() if hasattr(py, "asList") else py
                eng = PluginsController.engines.get("python")
                nested = None
                if eng:
                    try:
                        nested = eng.parsePySettingDefinitions(nested_src)
                    except:
                        nested = None
                if nested is None:
                    nested = nested_src
                _walk(nested, subprefix, text, depth + 1)
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
                itype = getattr(it, "type", None)
                key = getattr(it, "key", None)
                alias = getattr(it, "linkAlias", None)
                if key and itype in ("switch", "selector", "input", "edit_text"):
                    kp = f"{pf}:{key}" if pf else str(key)
                    op = _open_link_key(pf, str(key), alias)
                    if kp == target_full or op == target_open or (not pf and str(key) == target_value):
                        return it
                if itype != "text":
                    continue
                cb = getattr(it, "createSubFragmentCallback", None)
                if not cb:
                    continue
                raw_text = getattr(it, "text", getattr(it, "hint", str(key)))
                branch = alias or key or f"wizard_{depth}_{idx}_{_shortcut_norm_text(raw_text or '') or 'item'}"
                subprefix = str(branch) if not pf else f"{pf}:{branch}"
                if subprefix in visited_paths:
                    continue
                visited_paths.add(subprefix)
                py = _invoke_sub_fragment_callback(cb)
                nested_src = py.asList() if hasattr(py, "asList") else py
                eng = PluginsController.engines.get("python")
                nested = None
                if eng:
                    try:
                        nested = eng.parsePySettingDefinitions(nested_src)
                    except:
                        nested = None
                if nested is None:
                    nested = nested_src
                found = _walk(nested, subprefix, depth + 1)
                if found:
                    return found
            except Exception as e:
                log(f"[{__id__}] find setting item: {e}")
        return None

    try:
        return _walk(_get_settings_list(pid, ensure_loaded=True), "", 0)
    except Exception as e:
        log(f"[{__id__}] find setting item root: {e}")
        return None

def _trigger_setting_on_change(pid, sc, value):
    try:
        item = _find_setting_item(pid, sc)
        cb = getattr(item, "onChangeCallback", None) if item else None
        if not cb:
            return
        def _call():
            try:
                cb.call(value)
            except Exception as e:
                log(f"[{__id__}] on_change callback {pid}:{_setting_value_key(sc)}: {e}")
        _run_on_plugins_queue(_call)
    except Exception as e:
        log(f"[{__id__}] trigger on_change: {e}")
