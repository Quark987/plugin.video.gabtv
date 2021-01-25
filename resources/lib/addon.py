# -*- coding: utf-8 -*-
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""This is the actual Gab TV video plugin entry point"""

from __future__ import absolute_import, division, unicode_literals
from routing import Plugin
from xbmc import Keyboard

try:  # Python 3
    from urllib.parse import unquote_plus
except ImportError:  # Python 2
    from urllib import unquote_plus

from kodiutils import end_of_directory, execute_builtin, get_global_setting, localize, log_access, notification, ok_dialog
from kodiutils import from_unicode, to_unicode

plugin = Plugin()


@plugin.route('/')
def main_menu():
    """The Gab TV plugin main menu"""
    from gab import GabTV
    GabTV().show_main_menu()


@plugin.route('/categories')
@plugin.route('/categories/<category>')
def categories(category=None):
    """The categories menu and listing"""
    from gab import GabTV
    GabTV().show_category_menu(category=category)


@plugin.route('/explore')
def explore():
    from gab import GabTV
    GabTV().show_explore_menu()


@plugin.route('/play_video/<channel>/<view>')
def play_video(channel, view):
    from gab import GabTV
    GabTV().play_video(channel, view)


@plugin.route('/search')
def search():
    kb = Keyboard()
    kb.doModal()            # Onscreen keyboard appears
    if not kb.isConfirmed():
        return

    query = kb.getText()    # User input

    from gab import GabTV
    GabTV().show_search_results(query)


@plugin.route('/find_fanart/<image>')
def find_fanart(image):
    ok_dialog('tis van datte', 'find_fanart')


def run(argv):
    """Addon entry point from wrapper"""
    log_access(argv)
    plugin.run(argv)