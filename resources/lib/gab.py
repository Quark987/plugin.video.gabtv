from urllib import urlencode, quote
from kodiutils import url_for, localize, show_listing, ok_dialog
from helperobjects import TitleItem
import webscraper
import xbmc
import xbmcplugin
from xbmcgui import Dialog, ListItem
from addon import plugin

class GabTV(object):

    def __init__(self):
        # self.session = requests.session()
        pass


    def show_main_menu(self):
        """The Gab TV add-on main menu"""

        main_items = [
            TitleItem(label=localize(30010),  # Categories
                      path=url_for('categories'),
                      art_dict=dict(thumb='DefaultGenre.png'),
                      info_dict=dict(plot=localize(30011))),
            TitleItem(label=localize(30012),  # Explore
                      path=url_for('explore'),
                      art_dict=dict(thumb='DefaultCountry.png'),
                      info_dict=dict(plot=localize(30013))),
            TitleItem(label=localize(30014),  # Search
                      path=url_for('search'),
                      art_dict=dict(thumb='DefaultAddonsSearch.png'),
                      info_dict=dict(plot=localize(30015))),
        ]

        show_listing(main_items, cache=False)
    

    def show_explore_menu(self):
        video_items = webscraper.scrape_explore_menu()
        # ok_dialog('art url', video_items[0].art_dict['thumb'])
        show_listing(video_items, category=30012, sort='label', content='videos')  # A-Z
    

    def show_search_results(self, query):
        video_items = webscraper.scrape_search_results(query)
        show_listing(video_items, category=30014, sort='label', content='videos')


    def show_category_menu(self, category=None):
        if category:
            category_items = webscraper.scrape_category(category)
            show_listing(category_items, category=category, sort='label', content='videos')
        else:
            category_items = webscraper.list_categories()
            show_listing(category_items, category=30010, sort='unsorted', content='images') 


    def play_video(self, channel, view):
        url = webscraper.retrieve_video_url(channel, view)
        play_item = ListItem(path=url)
        xbmcplugin.setResolvedUrl(plugin.handle, bool(url), listitem=play_item)
    
