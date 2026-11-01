"""Single-message navigation for Gutter Saints player dashboards.

Component callbacks replace their own Discord interaction message. Any old
attachments and embeds are cleared, unless the replacement supplies new art.
"""
async def edit_panel(interaction, *, content=None, embed=None, view=None, file=None):
    await interaction.response.edit_message(content=content, embed=embed,
        attachments=[file] if file is not None else [], view=view)

async def modal_panel(interaction, *, content=None, embed=None, view=None, file=None):
    # Modal-submit interactions normally carry the message that opened them.
    # Fall back to a single ephemeral reply only if Discord supplies none.
    if getattr(interaction,'message',None) is not None:
        await edit_panel(interaction,content=content,embed=embed,view=view,file=file)
    else:
        await interaction.response.send_message(content=content,embed=embed,view=view,file=file,ephemeral=True)

async def menu_home(interaction):
    from cogs.menu import PublicMenu, admin_ok
    await edit_panel(interaction,
        content='🎳 **THE GUTTER SAINTS**\nBowling, careers, achievements and tournament control.',
        view=PublicMenu(admin=admin_ok(interaction)))
