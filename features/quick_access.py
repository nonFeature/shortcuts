from base_plugin import MenuItemData, MenuItemType

def update_quick_access(plugin, enabled=None):
    if enabled is None:
        enabled = bool(plugin.get_setting("quick_access", False))
    if enabled:
        if not plugin._qa_mid:
            plugin._qa_mid = plugin.add_menu_item(MenuItemData(
                menu_type=MenuItemType.DRAWER_MENU,
                text=_s("shortcuts"),
                icon="media_settings",
                priority=99,
                on_click=lambda ctx: plugin._open_self_settings()
            ))
    else:
        if plugin._qa_mid:
            try:
                plugin.remove_menu_item(plugin._qa_mid)
            except:
                pass
            plugin._qa_mid = None
