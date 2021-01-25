# -*- coding: utf-8 -*-
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""All functionality that requires Kodi imports"""

from __future__ import absolute_import, division, unicode_literals
from contextlib import contextmanager
from sys import version_info
from socket import timeout
from ssl import SSLError

import xbmc
import xbmcplugin

try:  # Kodi 19 alpha 2 and higher
    from xbmcvfs import translatePath
except ImportError:  # Kodi 19 alpha 1 and lower
    from xbmc import translatePath  # pylint: disable=ungrouped-imports

from xbmcaddon import Addon

try:  # Python 3
    from urllib.request import HTTPErrorProcessor
except ImportError:  # Python 2
    from urllib2 import HTTPErrorProcessor

ADDON = Addon()
DEFAULT_CACHE_DIR = 'cache'

SORT_METHODS = dict(
    # date=xbmcplugin.SORT_METHOD_DATE,
    dateadded=xbmcplugin.SORT_METHOD_DATEADDED,
    duration=xbmcplugin.SORT_METHOD_DURATION,
    episode=xbmcplugin.SORT_METHOD_EPISODE,
    # genre=xbmcplugin.SORT_METHOD_GENRE,
    # label=xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
    label=xbmcplugin.SORT_METHOD_LABEL,
    title=xbmcplugin.SORT_METHOD_TITLE,
    # none=xbmcplugin.SORT_METHOD_UNSORTED,
    # FIXME: We would like to be able to sort by unprefixed title (ignore date/episode prefix)
    # title=xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE,
    unsorted=xbmcplugin.SORT_METHOD_UNSORTED,
)


class NoRedirection(HTTPErrorProcessor):
    """Prevent urllib from following http redirects"""

    def http_response(self, request, response):
        return response

    https_response = http_response


class SafeDict(dict):
    """A safe dictionary implementation that does not break down on missing keys"""
    def __missing__(self, key):
        """Replace missing keys with the original placeholder"""
        return '{' + key + '}'


def to_unicode(text, encoding='utf-8', errors='strict'):
    """Force text to unicode"""
    if isinstance(text, bytes):
        return text.decode(encoding, errors=errors)
    return text


def from_unicode(text, encoding='utf-8', errors='strict'):
    """Force unicode to text"""
    import sys
    if sys.version_info.major == 2 and isinstance(text, unicode):  # noqa: F821; pylint: disable=undefined-variable
        return text.encode(encoding, errors)
    return text


def addon_icon():
    """Return add-on icon"""
    return get_addon_info('icon')


def addon_id():
    """Return add-on ID"""
    return get_addon_info('id')


def addon_fanart():
    """Return add-on fanart"""
    return get_addon_info('fanart')


def addon_name():
    """Return add-on name"""
    return get_addon_info('name')


def addon_path():
    """Return add-on path"""
    return get_addon_info('path')


def translate_path(path):
    """Converts a Kodi special:// path to the corresponding OS-specific path"""
    return to_unicode(translatePath(from_unicode(path)))


def addon_profile():
    """Return add-on profile"""
    return translate_path(ADDON.getAddonInfo('profile'))


def url_for(name, *args, **kwargs):
    """Wrapper for routing.url_for() to lookup by name"""
    import addon
    return addon.plugin.url_for(getattr(addon, name), *args, **kwargs)


def show_listing(list_items, category=None, sort='unsorted', ascending=True, content=None, cache=None, selected=None):
    """Show a virtual directory in Kodi"""
    from xbmcgui import ListItem
    from addon import plugin

    set_property('container.url', 'plugin://' + addon_id() + plugin.path)
    xbmcplugin.setPluginFanart(handle=plugin.handle, image=from_unicode(addon_fanart()))

    usemenucaching = get_setting_bool('usemenucaching', default=True)
    if cache is None:
        cache = usemenucaching
    elif usemenucaching is False:
        cache = False

    if content:
        # content is one of: files, songs, artists, albums, movies, videos, episodes, musicvideos
        xbmcplugin.setContent(plugin.handle, content=content)

    # Jump through hoops to get a stable breadcrumbs implementation
    category_label = ''
    if category:
        if not content:
            category_label = 'Gab TV / '
        if plugin.path.startswith(('/favorites/', '/resumepoints/')):
            category_label += localize(30428) + ' / '  # My
        if isinstance(category, int):
            category_label += localize(category)
        else:
            category_label += category
    elif not content:
        category_label = 'Gab TV'
    xbmcplugin.setPluginCategory(handle=plugin.handle, category=category_label)

    # FIXME: Since there is no way to influence descending order, we force it here
    if not ascending:
        sort = 'unsorted'

    # NOTE: When showing video listings and 'showoneoff' was set, force 'unsorted'
    if get_setting_bool('showoneoff', default=True) and sort == 'label' and content == 'videos':
        sort = 'unsorted'

    # Add all sort methods to GUI (start with preferred)
    xbmcplugin.addSortMethod(handle=plugin.handle, sortMethod=SORT_METHODS[sort])
    for key in sorted(SORT_METHODS):
        if key != sort:
            xbmcplugin.addSortMethod(handle=plugin.handle, sortMethod=SORT_METHODS[key])

    # FIXME: This does not appear to be working, we have to order it ourselves
#    xbmcplugin.setProperty(handle=plugin.handle, key='sort.ascending', value='true' if ascending else 'false')
#    if ascending:
#        xbmcplugin.setProperty(handle=plugin.handle, key='sort.order', value=str(SORT_METHODS[sort]))
#    else:
#        # NOTE: When descending, use unsorted
#        xbmcplugin.setProperty(handle=plugin.handle, key='sort.order', value=str(SORT_METHODS['unsorted']))

    listing = []
    showfanart = get_setting_bool('showfanart', default=True)
    for title_item in list_items:
        # Three options:
        #  - item is a virtual directory/folder (not playable, path)
        #  - item is a playable file (playable, path)
        #  - item is non-actionable item (not playable, no path)
        is_folder = bool(not title_item.is_playable and title_item.path)
        is_playable = bool(title_item.is_playable and title_item.path)

        list_item = ListItem(label=title_item.label)

        prop_dict = dict(
            IsInternetStream='true' if is_playable else 'false',
            IsPlayable='true' if is_playable else 'false',
            IsFolder='false' if is_folder else 'true',
        )
        if title_item.prop_dict:
            title_item.prop_dict.update(prop_dict)
        else:
            title_item.prop_dict = prop_dict
        # NOTE: The setProperties method is new in Kodi18
        try:
            list_item.setProperties(title_item.prop_dict)
        except AttributeError:
            for key, value in list(title_item.prop_dict.items()):
                list_item.setProperty(key=key, value=str(value))

        # FIXME: The setIsFolder method is new in Kodi18, so we cannot use it just yet
        # list_item.setIsFolder(is_folder)

        if showfanart:
            # Add add-on fanart when fanart is missing
            if not title_item.art_dict:
                title_item.art_dict = dict(fanart=addon_fanart())
            elif not title_item.art_dict.get('fanart'):
                title_item.art_dict.update(fanart=addon_fanart())
            list_item.setArt(title_item.art_dict)

        if title_item.info_dict:
            # type is one of: video, music, pictures, game
            list_item.setInfo(type='video', infoLabels=title_item.info_dict)

        if title_item.stream_dict:
            # type is one of: video, audio, subtitle
            list_item.addStreamInfo('video', title_item.stream_dict)

        if title_item.context_menu:
            list_item.addContextMenuItems(title_item.context_menu)

        url = None
        if title_item.path:
            url = title_item.path

        # list_item.setMimeType('image/apng')
        listing.append((url, list_item, is_folder))

    # Jump to specific item
    if selected is not None:
        pass
#        from xbmcgui import getCurrentWindowId, Window
#        wnd = Window(getCurrentWindowId())
#        wnd.getControl(wnd.getFocusId()).selectItem(selected)

    succeeded = xbmcplugin.addDirectoryItems(plugin.handle, listing, len(listing))
    xbmcplugin.endOfDirectory(plugin.handle, succeeded, updateListing=False, cacheToDisc=cache)


def play(stream, video=None):
    """Create a virtual directory listing to play its only item"""
    try:  # Python 3
        from urllib.parse import unquote
    except ImportError:  # Python 2
        from urllib2 import unquote

    from xbmcgui import ListItem
    from addon import plugin

    play_item = ListItem(path=stream.stream_url)
    if video and hasattr(video, 'info_dict'):
        play_item.setProperty('subtitle', video.label)
        play_item.setArt(video.art_dict)
        play_item.setInfo(
            type='video',
            infoLabels=video.info_dict
        )
    play_item.setProperty('inputstream.adaptive.max_bandwidth', str(get_max_bandwidth() * 1000))
    play_item.setProperty('network.bandwidth', str(get_max_bandwidth() * 1000))

    if stream.stream_url is not None and stream.use_inputstream_adaptive:
        if kodi_version_major() < 19:
            play_item.setProperty('inputstreamaddon', 'inputstream.adaptive')
        else:
            play_item.setProperty('inputstream', 'inputstream.adaptive')

        play_item.setContentLookup(False)

        if '.mpd' in stream.stream_url:
            play_item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
            play_item.setMimeType('application/dash+xml')

        if '.m3u8' in stream.stream_url:
            play_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
            play_item.setMimeType('application/vnd.apple.mpegurl')

        if stream.license_key is not None:
            import inputstreamhelper
            is_helper = inputstreamhelper.Helper('mpd', drm='com.widevine.alpha')
            if is_helper.check_inputstream():
                play_item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
                play_item.setProperty('inputstream.adaptive.license_key', stream.license_key)

    subtitles_visible = get_setting_bool('showsubtitles', default=True)
    # Separate subtitle url for hls-streams
    if subtitles_visible and stream.subtitle_url is not None:
        log(2, 'Subtitle URL: {url}', url=unquote(stream.subtitle_url))
        play_item.setSubtitles([stream.subtitle_url])

    log(1, 'Play: {url}', url=unquote(stream.stream_url))
    xbmcplugin.setResolvedUrl(plugin.handle, bool(stream.stream_url), listitem=play_item)

    while not xbmc.Player().isPlaying() and not xbmc.Monitor().abortRequested():
        xbmc.sleep(100)
    xbmc.Player().showSubtitles(subtitles_visible)


def get_search_string(search_string=None):
    """Ask the user for a search string"""
    keyboard = xbmc.Keyboard(search_string, localize(30134))
    keyboard.doModal()
    if keyboard.isConfirmed():
        search_string = to_unicode(keyboard.getText())
    return search_string


def ok_dialog(heading='', message=''):
    """Show Kodi's OK dialog"""
    from xbmcgui import Dialog
    if not heading:
        heading = addon_name()
    if kodi_version_major() < 19:
        return Dialog().ok(heading=heading, line1=message)
    return Dialog().ok(heading=heading, message=message)


def notification(heading='', message='', icon='info', time=4000):
    """Show a Kodi notification"""
    from xbmcgui import Dialog
    if not heading:
        heading = addon_name()
    if not icon:
        icon = addon_icon()
    Dialog().notification(heading=heading, message=message, icon=icon, time=time)


def multiselect(heading='', options=None, autoclose=0, preselect=None, use_details=False):
    """Show a Kodi multi-select dialog"""
    from xbmcgui import Dialog
    if not heading:
        heading = addon_name()
    return Dialog().multiselect(heading=heading, options=options, autoclose=autoclose, preselect=preselect, useDetails=use_details)


def set_locale():
    """Load the proper locale for date strings, only once"""
    if hasattr(set_locale, 'cached'):
        return getattr(set_locale, 'cached')
    from locale import Error, LC_ALL, setlocale
    locale_lang = get_global_setting('locale.language').split('.')[-1]
    locale_lang = locale_lang[:-2] + locale_lang[-2:].upper()
    # NOTE: setlocale() only works if the platform supports the Kodi configured locale
    try:
        setlocale(LC_ALL, locale_lang)
    except (Error, ValueError) as exc:
        if locale_lang != 'en_GB':
            log(3, "Your system does not support locale '{locale}': {error}", locale=locale_lang, error=exc)
            set_locale.cached = False
            return False
    set_locale.cached = True
    return True


def localize(string_id, **kwargs):
    """Return the translated string from the .po language files, optionally translating variables"""
    if not isinstance(string_id, int) and not string_id.isdecimal():
        return string_id
    if kwargs:
        from string import Formatter
        return Formatter().vformat(ADDON.getLocalizedString(string_id), (), SafeDict(**kwargs))
    return ADDON.getLocalizedString(string_id)


def localize_time(time):
    """Localize time format"""
    time_format = xbmc.getRegion('time')

    # Fix a bug in Kodi v18.5 and older causing double hours
    # https://github.com/xbmc/xbmc/pull/17380
    time_format = time_format.replace('%H%H:', '%H:')

    # Strip off seconds
    time_format = time_format.replace(':%S', '')

    return time.strftime(time_format)


def get_setting(key, default=None):
    """Get an add-on setting as string"""
    try:
        value = to_unicode(ADDON.getSetting(key))
    except RuntimeError:  # Occurs when the add-on is disabled
        return default
    if value == '' and default is not None:
        return default
    return value


def get_setting_bool(key, default=None):
    """Get an add-on setting as boolean"""
    try:
        return ADDON.getSettingBool(key)
    except (AttributeError, TypeError):  # On Krypton or older, or when not a boolean
        value = get_setting(key, default)
        if value not in ('false', 'true'):
            return default
        return bool(value == 'true')
    except RuntimeError:  # Occurs when the add-on is disabled
        return default


def get_setting_int(key, default=None):
    """Get an add-on setting as integer"""
    try:
        return ADDON.getSettingInt(key)
    except (AttributeError, TypeError):  # On Krypton or older, or when not an integer
        value = get_setting(key, default)
        try:
            return int(value)
        except ValueError:
            return default
    except RuntimeError:  # Occurs when the add-on is disabled
        return default


def get_setting_float(key, default=None):
    """Get an add-on setting as float"""
    value = get_setting(key, default)
    try:
        return float(value)
    except ValueError:
        return default
    except RuntimeError:  # Occurs when the add-on is disabled
        return default


def set_setting(key, value):
    """Set an add-on setting"""
    return ADDON.setSetting(key, from_unicode(str(value)))


def set_setting_bool(key, value):
    """Set an add-on setting as boolean"""
    try:
        return ADDON.setSettingBool(key, value)
    except (AttributeError, TypeError):  # On Krypton or older, or when not a boolean
        if value in ['false', 'true']:
            return set_setting(key, value)
        if value:
            return set_setting(key, 'true')
        return set_setting(key, 'false')


def set_setting_int(key, value):
    """Set an add-on setting as integer"""
    try:
        return ADDON.setSettingInt(key, value)
    except (AttributeError, TypeError):  # On Krypton or older, or when not an integer
        return set_setting(key, value)


def set_setting_float(key, value):
    """Set an add-on setting"""
    try:
        return ADDON.setSettingNumber(key, value)
    except (AttributeError, TypeError):  # On Krypton or older, or when not a float
        return set_setting(key, value)


def open_settings():
    """Open the add-in settings window, shows Credentials"""
    ADDON.openSettings()


def get_global_setting(key):
    """Get a Kodi setting"""
    result = jsonrpc(method='Settings.GetSettingValue', params=dict(setting=key))
    return result.get('result', {}).get('value')


def get_advanced_setting(key, default=None):
    """Get a setting from advancedsettings.xml"""
    as_path = translate_path('special://masterprofile/advancedsettings.xml')
    if not exists(as_path):
        return default
    from xml.etree.ElementTree import parse, ParseError
    try:
        as_root = parse(as_path).getroot()
    except ParseError:
        return default
    value = as_root.find(key)
    if value is not None:
        if value.text is None:
            return default
        return value.text
    return default


def get_advanced_setting_int(key, default=0):
    """Get a setting from advancedsettings.xml as an integer"""
    if not isinstance(default, int):
        default = 0
    setting = get_advanced_setting(key, default)
    if not isinstance(setting, int):
        setting = int(setting.strip()) if setting.strip().isdigit() else default
    return setting


def get_property(key, default=None, window_id=10000):
    """Get a Window property"""
    from xbmcgui import Window
    value = to_unicode(Window(window_id).getProperty(key))
    if value == '' and default is not None:
        return default
    return value


def set_property(key, value, window_id=10000):
    """Set a Window property"""
    from xbmcgui import Window
    return Window(window_id).setProperty(key, from_unicode(value))


def clear_property(key, window_id=10000):
    """Clear a Window property"""
    from xbmcgui import Window
    return Window(window_id).clearProperty(key)


def notify(sender, message, data):
    """Send a notification to Kodi using JSON RPC"""
    result = jsonrpc(method='JSONRPC.NotifyAll', params=dict(
        sender=sender,
        message=message,
        data=data,
    ))
    if result.get('result') != 'OK':
        log_error('Failed to send notification: {error}', error=result.get('error').get('message'))
        return False
    log(2, 'Succesfully sent notification')
    return True


def get_playerid():
    """Get current playerid"""
    result = dict()
    while not result.get('result'):
        result = jsonrpc(method='Player.GetActivePlayers')
    return result.get('result', [{}])[0].get('playerid')


def get_max_bandwidth():
    """Get the max bandwidth based on Kodi and add-on settings"""
    gabtv_max_bandwidth = int(get_setting('max_bandwidth', default='0'))
    global_max_bandwidth = int(get_global_setting('network.bandwidth'))
    if gabtv_max_bandwidth != 0 and global_max_bandwidth != 0:
        return min(gabtv_max_bandwidth, global_max_bandwidth)
    if gabtv_max_bandwidth != 0:
        return gabtv_max_bandwidth
    if global_max_bandwidth != 0:
        return global_max_bandwidth
    return 0


def get_cond_visibility(condition):
    """Test a condition in XBMC"""
    return xbmc.getCondVisibility(condition)


def has_inputstream_adaptive():
    """Whether InputStream Adaptive is installed and enabled in add-on settings"""
    return get_setting_bool('useinputstreamadaptive', default=True) and has_addon('inputstream.adaptive')


def has_addon(name):
    """Checks if add-on is installed and enabled"""
    if kodi_version_major() < 19:
        return xbmc.getCondVisibility('System.HasAddon(%s)' % name) == 1
    return xbmc.getCondVisibility('System.AddonIsEnabled(%s)' % name) == 1


def kodi_version():
    """Returns full Kodi version as string"""
    return xbmc.getInfoLabel('System.BuildVersion').split(' ')[0]


def kodi_version_major():
    """Returns major Kodi version as integer"""
    return int(kodi_version().split('.')[0])


def can_play_drm():
    """Whether this Kodi can do DRM using InputStream Adaptive"""
    return get_setting_bool('usedrm', default=True) and get_setting_bool('useinputstreamadaptive', default=True) and supports_drm()


def supports_drm():
    """Whether this Kodi version supports DRM decryption using InputStream Adaptive"""
    return kodi_version_major() > 17


COLOUR_THEMES = dict(
    dark=dict(highlighted='yellow', availability='blue', geoblocked='red', greyedout='gray'),
    light=dict(highlighted='brown', availability='darkblue', geoblocked='darkred', greyedout='darkgray'),
    custom=dict(
        highlighted=get_setting('colour_highlighted'),
        availability=get_setting('colour_availability'),
        geoblocked=get_setting('colour_geoblocked'),
        greyedout=get_setting('colour_greyedout')
    )
)


def themecolour(kind):
    """Get current theme color by kind (highlighted, availability, geoblocked, greyedout)"""
    theme = get_setting('colour_theme', 'dark')
    color = COLOUR_THEMES.get(theme).get(kind, COLOUR_THEMES.get('dark').get(kind))
    return color


def colour(text):
    """Convert stub color bbcode into colors from the settings"""
    theme = get_setting('colour_theme', 'dark')
    text = text.format(**COLOUR_THEMES.get(theme))
    return text


def get_cache_path(cache_file, cache_dir=DEFAULT_CACHE_DIR):
    """Return a specified cache path"""
    import os
    cache_dir = get_cache_dir(cache_dir)
    return os.path.join(cache_dir, cache_file)


def get_cache_dir(cache_dir=DEFAULT_CACHE_DIR):
    """Create and return a specified cache directory"""
    import os
    cache_dir = os.path.join(addon_profile(), cache_dir, '')
    return cache_dir


def get_addon_info(key):
    """Return addon information"""
    return to_unicode(ADDON.getAddonInfo(key))


def listdir(path):
    """Return all files in a directory (using xbmcvfs)"""
    from xbmcvfs import listdir as vfslistdir
    return vfslistdir(path)


def mkdir(path):
    """Create a directory (using xbmcvfs)"""
    from xbmcvfs import mkdir as vfsmkdir
    log(3, "Create directory '{path}'.", path=path)
    return vfsmkdir(path)


def mkdirs(path):
    """Create directory including parents (using xbmcvfs)"""
    from xbmcvfs import mkdirs as vfsmkdirs
    log(3, "Recursively create directory '{path}'.", path=path)
    return vfsmkdirs(path)


def exists(path):
    """Whether the path exists (using xbmcvfs)"""
    from xbmcvfs import exists as vfsexists
    return vfsexists(path)


@contextmanager
def open_file(path, flags='r'):
    """Open a file (using xbmcvfs)"""
    from xbmcvfs import File
    fdesc = File(path, flags)
    yield fdesc
    fdesc.close()


def stat_file(path):
    """Return information about a file (using xbmcvfs)"""
    from xbmcvfs import Stat
    return Stat(path)


def delete(path):
    """Remove a file (using xbmcvfs)"""
    from xbmcvfs import delete as vfsdelete
    log(3, "Delete file '{path}'.", path=path)
    return vfsdelete(path)


def delete_cached_thumbnail(url):
    """Remove a cached thumbnail from Kodi in an attempt to get a realtime live screenshot"""
    # Get texture
    result = jsonrpc(method='Textures.GetTextures', params=dict(
        filter=dict(
            field='url',
            operator='is',
            value=url,
        ),
    ))
    if result.get('result', {}).get('textures') is None:
        log_error('URL {url} not found in texture cache', url=url)
        return False

    texture_id = next((texture.get('textureid') for texture in result.get('result').get('textures')), None)
    if not texture_id:
        log_error('URL {url} not found in texture cache', url=url)
        return False
    log(2, 'found texture_id {id} for url {url} in texture cache', id=texture_id, url=url)

    # Remove texture
    result = jsonrpc(method='Textures.RemoveTexture', params=dict(textureid=texture_id))
    if result.get('result') != 'OK':
        log_error('failed to remove {url} from texture cache: {error}', url=url, error=result.get('error', {}).get('message'))
        return False

    log(2, 'succesfully removed {url} from texture cache', url=url)
    return True


def input_down():
    """Move the cursor down"""
    jsonrpc(method='Input.Down')


def current_container_url():
    """Get current container plugin:// url"""
    url = xbmc.getInfoLabel('Container.FolderPath')
    if url == '':
        return None
    return url


def container_refresh(url=None):
    """Refresh the current container or (re)load a container by URL"""
    if url:
        log(3, 'Execute: Container.Refresh({url})', url=url)
        xbmc.executebuiltin('Container.Refresh({url})'.format(url=url))
    else:
        log(3, 'Execute: Container.Refresh')
        xbmc.executebuiltin('Container.Refresh')


def container_update(url):
    """Update the current container while respecting the path history."""
    if url:
        log(3, 'Execute: Container.Update({url})', url=url)
        xbmc.executebuiltin('Container.Update({url})'.format(url=url))
    else:
        # URL is a mandatory argument for Container.Update, use Container.Refresh instead
        container_refresh()


def container_reload(url=None):
    """Only update container if the play action was initiated from it"""
    if url is None:
        url = get_property('container.url')
    if current_container_url() != url:
        return
    container_update(url)


def execute_builtin(builtin):
    """Run an internal Kodi builtin"""
    xbmc.executebuiltin(builtin)


def end_of_directory():
    """Close a virtual directory, required to avoid a waiting Kodi"""
    from addon import plugin
    xbmcplugin.endOfDirectory(handle=plugin.handle, succeeded=False, updateListing=False, cacheToDisc=False)


def log(level=1, message='', **kwargs):
    """Log info messages to Kodi"""
    debug_logging = get_global_setting('debug.showloginfo')  # Returns a boolean
    max_log_level = get_setting_int('max_log_level', default=0)
    if not debug_logging and not (level <= max_log_level and max_log_level != 0):
        return
    if kwargs:
        from string import Formatter
        message = Formatter().vformat(message, (), SafeDict(**kwargs))
    message = '[{addon}] {message}'.format(addon=addon_id(), message=message)
    xbmc.log(from_unicode(message), level % 3 if debug_logging else 2)


def log_access(argv):
    """Log addon access"""
    log(1, 'Access: {url}{qs}', url=argv[0], qs=argv[2] if len(argv) > 2 else '')


def log_error(message, **kwargs):
    """Log error messages to Kodi"""
    if kwargs:
        from string import Formatter
        message = Formatter().vformat(message, (), SafeDict(**kwargs))
    message = '[{addon}] {message}'.format(addon=addon_id(), message=message)
    xbmc.log(from_unicode(message), 4)


def jsonrpc(*args, **kwargs):
    """Perform JSONRPC calls"""
    from json import dumps, loads

    # We do not accept both args and kwargs
    if args and kwargs:
        log_error('Wrong use of jsonrpc()')
        return None

    # Process a list of actions
    if args:
        for (idx, cmd) in enumerate(args):
            if cmd.get('id') is None:
                cmd.update(id=idx)
            if cmd.get('jsonrpc') is None:
                cmd.update(jsonrpc='2.0')
        return loads(xbmc.executeJSONRPC(dumps(args)))

    # Process a single action
    if kwargs.get('id') is None:
        kwargs.update(id=0)
    if kwargs.get('jsonrpc') is None:
        kwargs.update(jsonrpc='2.0')
    return loads(xbmc.executeJSONRPC(dumps(kwargs)))
