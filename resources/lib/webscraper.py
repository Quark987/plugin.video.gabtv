import os
import xbmc
from helperobjects import TitleItem
from kodiutils import url_for, log, ok_dialog, ADDON, get_setting
import requests
from bs4 import BeautifulSoup

try:  # Python 3
    from urllib.error import HTTPError
    from urllib.parse import quote, urlencode
except ImportError:  # Python 2
    from urllib import urlencode
    from urllib2 import quote, HTTPError


BASE_URL = 'https://tv.gab.com'
headers = {"User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36 OPR/67.0.3575.137"}
session = requests.session()


def kodi_header():
        header = ''             # This is to transmit the cookie in Kodi format
        for element in session.cookies.get_dict():
            header += element + '=' + session.cookies[element] + ';'
        header = header[:-1]    # Drop trailing semicolon

        return '|'+'Cookie='+quote(header)+'&'+urlencode(session.headers)


def scrape_search_results(query):
    page = session.get(BASE_URL+'/search?q'+urlencode({'':query}), headers=headers)
    soup = BeautifulSoup(page.content, 'html.parser')
    results = soup.find('div', class_='uk-grid-small uk-flex-center').findChildren('div', recursive=False)

    art_urls = []
    video_urls = []
    titles = []

    for result in results:
        art_urls.append(   BASE_URL + result.find('div', class_='studio-episode-thumbnail').find('img').get('src'))
        video_urls.append( result.find('div').get('data-episode-url'))
        titles.append(     result.find('div').get('title'))
    
    return __map_videos(titles, video_urls, art_urls)


def scrape_explore_menu():
    page = session.get(BASE_URL, headers=headers)
    soup = BeautifulSoup(page.content, 'html.parser')
    results = soup.find('div', class_='uk-grid-small uk-flex-center').findChildren('div', recursive=False)

    art_urls = []
    video_urls = []
    titles = []

    for result in results:
        art_urls.append(   BASE_URL + result.find('div', class_='studio-episode-thumbnail').find('img').get('src'))
        video_urls.append( result.find('div').get('data-episode-url'))
        titles.append(     result.find('div').get('title'))
    
    return __map_videos(titles, video_urls, art_urls)


def list_categories():
    page = session.get(BASE_URL + '/category', headers=headers)
    soup = BeautifulSoup(page.content, 'html.parser')
    results = soup.find('div', class_='uk-flex-center').findChildren('div', recursive=False)

    category_items = []

    for result in results:
        art_url = BASE_URL + result.find('img').get('src')
        art_url = download_fanart(art_url)

        label = result.find('div', class_='uk-text-bold uk-text-truncate').contents[0]
        category = result.find('a').get('href').split('/')[-1]
        art_dict = {'thumb' : art_url,
                    'fanart':art_url,
                    'icon'  :art_url}

        category_items.append(TitleItem(
            label=label,
            path=url_for('categories', category=category),
            art_dict=art_dict,
        ))

    return category_items


def scrape_category(category):
    page = session.get(BASE_URL+'/category/'+category, headers=headers)
    soup = BeautifulSoup(page.content, 'html.parser')
    results = soup.find_all('div', class_='uk-width-1-1 uk-width-1-2@s uk-width-1-3@m uk-width-1-4@l uk-width-1-5@xl')

    art_urls = []
    video_urls = []
    titles = []

    for result in results:
        art_urls.append(   BASE_URL + result.find('div', class_='studio-episode-thumbnail').find('img').get('src')) 
        video_urls.append( result.find('div').get('data-episode-url'))
        titles.append(     result.find('div').get('title'))
    
    return __map_videos(titles, video_urls, art_urls)


def retrieve_video_url(channel, view):
    url = BASE_URL + '/channel/' + channel + '/view/' + view
    page = session.get(url, headers=headers)
    soup = BeautifulSoup(page.content, 'html.parser')

    media = soup.find('meta', attrs={'property':'og:video'}).get('content')
    view_key = soup.find('div', class_='studio-player').get('data-view-key')
    resolution = '1080p'

    return media + '?viewKey=' + view_key + '&r=' + resolution + kodi_header()


def __map_videos(titles, video_urls, art_urls):
    """Construct a list of videos"""
    items = []

    for title, video_url, art_url in zip(titles, video_urls, art_urls):
        channel = video_url.split('/')[2]
        view = video_url.split('/')[4]

        # Download art and use local file, a workaround as 'content-type' is 'undefined' in the response header
        art_url = download_fanart(art_url)  

        art_dict = {'thumb' : art_url,
                    'fanart': art_url,
                    'icon'  : art_url}
        
        items.append(TitleItem( label=title,
                                path=url_for('play_video', channel=channel, view=view),
                                art_dict=art_dict,
                                info_dict=dict(plot="Title: "+title+'\nChannel: '+channel),
                                is_playable=True))

    return items


def sorted_ls(path):
    mtime = lambda f: os.stat(os.path.join(path, f)).st_mtime
    return list(sorted(os.listdir(path), key=mtime))


def download_fanart(url):
    key = url.split('/')[-1]
    addon_dir = xbmc.translatePath( ADDON.getAddonInfo('path') )
    path = os.path.join(addon_dir, 'resources', 'thumbnails')

    filename = ''
    exists = False
    for s in os.listdir(path):
        if os.path.splitext(s)[0] == 'gabtv_' + key:
            filename = os.path.join(addon_dir, 'resources', 'thumbnails', s)
            exists = True
            break

    if not exists:
        response = requests.get(url)

        try:
            extension = response.headers['Content-Type'].split('/')[-1]
        except:
            extension = 'apng'

        filename = os.path.join(addon_dir, 'resources', 'thumbnails', 'gabtv_' + key + "." + extension) 

        file = open(filename, "wb")
        file.write(response.content)
        file.close()


    max_Files = int(get_setting('cache_size'))    # Limit the number of cached images, otherwise the space required will be too much
    del_list = sorted_ls(path)[0:(len(sorted_ls(path))-max_Files)]
    for dfile in del_list:
        os.remove(path + '/' + dfile)

    return filename