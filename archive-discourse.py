#!/bin/python3
# Archive a Discourse
# https://github.com/kitsandkats/ArchiveDiscourse
#
# Forked and adapted from: https://github.com/mcmcclur/ArchiveDiscourse

# The main code added to the original script is a
# way to get *all* posts in a topic (not just the first 20)
#
# The code is not perfect by any means, but it worked for my purposes!
#
# Be sure to define the base_url of the Discourse instance,
# the path of the directory to save stuff on the local machine,
# and an archive_blurb to describe the site.
#
# Note that the directory specified by `path` will be overwritten.
#
#
# It is recommended to run this code using Python 3 and a virtualenv.
# One place to learn more about how to do that is here:
# https://realpython.com/python-virtual-environments-a-primer/
#

from datetime import date, datetime
import os, requests, base64

# 
# TODO Make sure to customize these variables
# 
cookie_name = '_t'
cookie = ''
base_url = 'https://my-discourse'
path = os.path.join(os.getcwd(), 'export')
archive_blurb = "" # describe the site here
max_requests_per_min = 100 # set value to -1 to remove rate limits

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
from bs4 import BeautifulSoup as bs
from PIL import Image
from io import BytesIO
from time import sleep
from string import Template

from shutil import rmtree

# When archiving larger sites (like meta.discourse.org), you might need to
# increase the number of max_retries to connect.
# Doesn't seem to be necessary for all sites but it *is* necessary for Meta.

from requests.adapters import HTTPAdapter

s = requests.Session()
s.mount(base_url, HTTPAdapter(max_retries=5))

def throttle_requests():
    if max_requests_per_min > 0:
        sleep(60/max_requests_per_min)

# Copy the cookie from your browser if it's a private forum
jar = requests.cookies.RequestsCookieJar()
jar.set(cookie_name, cookie, domain=urlparse(base_url).hostname, path='/')

# Templates for the webpages
base_scheme = urlparse(base_url).scheme

# Template for the main page. Subsequent code will replace a few items indicated by
with open('templates/main.html', 'r') as main_file:
    main_template = main_file.read()

# Template for the individual category pages
with open('templates/category.html', 'r') as category_file:
    category_template = category_file.read()

# Template for the individual topic pages
with open('templates/topic.html', 'r') as topic_file:
    topic_template = topic_file.read()

# Load CSS
with open('archived.css', 'r') as css_file:
    css = css_file.read()

archive_notice = Template(
    'This is an archive of ' + 
    '<a href="$url">$hostname</a> ' +
    'captured on <time>$timestamp</time>.'
).safe_substitute(
    url=base_url,
    hostname=urlparse(base_url).hostname,
    timestamp=datetime.now().strftime("%c")
)

# Function that writes out each individual topic page
def write_topic(topic_json):
    topic_download_url = base_url + '/t/' + str(topic_json['id'])
    topic_relative_url = 't/'  + str(topic_json['id'])
    try:
        os.makedirs(topic_relative_url)
    except Exception as err:
        print ('in write_topic error:', 'make directory')

    response = requests.get(topic_download_url + '.json', cookies=jar)

    try:
        # posts_json will contain only the first 20 posts in a topic
        posts_json = response.json()['post_stream']['posts']
        # posts_stream will grab all of the post ids for that topic
        posts_stream = response.json()['post_stream']['stream']
        # get rid of first 20 in stream, as they are already in posts_json
        posts_stream = posts_stream[20:]
    except Exception as err:
        print ('in write_topic error:', topic_download_url + '.json')
        print (response.status_code)
        print (response.content)
        raise err

    # break stream into a list of list chunks of n posts each for lighter requests
    n = 20
    chunked_posts_stream = [posts_stream[i * n:(i + 1) * n] for i in range((len(posts_stream) + n - 1) // n)]
    posts_download_url = base_url + '/t/' + str(topic_json['id']) + '/posts.json?'
    # make a request for the content associated with each post id
    # chunk and append it to the posts_json list
    for chunk in chunked_posts_stream:
        formatted_posts_list = ""
        for post_id in chunk:
            formatted_posts_list = formatted_posts_list + 'post_ids[]=' + str(post_id) + '&'
        response = requests.get(posts_download_url + formatted_posts_list, cookies=jar)
        posts_2_json = response.json()['post_stream']['posts']
        posts_json.extend(posts_2_json)
    # generate that HTML
    post_list_string = ""
    for post_json in posts_json:
        post_list_string = post_list_string + post_row(post_json)
    topic_file_string = topic_template \
        .replace("<!-- TOPIC_TITLE -->", topic_json['fancy_title']) \
        .replace("<!-- SITE_TITLE -->", site_title) \
        .replace("<!-- ARCHIVE_NOTICE -->", archive_notice) \
        .replace("<!-- ARCHIVE_BLURB -->", archive_blurb) \
        .replace("/* HEADER_PRIMARY_COLOR */", '#' + info_json['header_primary_color']) \
        .replace("/* HEADER_BACKGROUND_COLOR */", '#' + info_json['header_background_color']) \
        .replace("<!-- POST_LIST -->", post_list_string)

    f = open(topic_relative_url + '/index.html', 'w')
    f.write(topic_file_string)
    f.close()


# Function that writes out each individual category page
def write_category(category_json):
    category_relative_url = 'c/'  + str(category_json['id'])
    try:
        os.makedirs(category_relative_url)
    except Exception as err:
        print ('in write_topic error:', 'make directory')
    
    # generate that HTML
    subcategory_list_string = ""
    for subcategory_json in (category_json.get('subcategory_list') or []):
        subcategory_list_string = subcategory_list_string + category_row(subcategory_json, '../../')
        write_category(subcategory_json)
    topic_list_string = ""
    for topic_json in (category_id_to_topics.get(category_json['id']) or []):
        topic_list_string = topic_list_string + topic_row(topic_json, '../../')
    category_file_string = category_template \
        .replace("<!-- CATEGORY_TITLE -->", category_json['name']) \
        .replace("<!-- CATEGORY_DESCRIPTION -->", (category_json['description'] or '')) \
        .replace("<!-- SITE_TITLE -->", site_title) \
        .replace("<!-- ARCHIVE_NOTICE -->", archive_notice) \
        .replace("<!-- ARCHIVE_BLURB -->", archive_blurb) \
        .replace("/* HEADER_PRIMARY_COLOR */", '#' + info_json['header_primary_color']) \
        .replace("/* HEADER_BACKGROUND_COLOR */", '#' + info_json['header_background_color']) \
        .replace("<!-- SUBCATEGORY_LIST -->", subcategory_list_string) \
        .replace("<!-- TOPIC_LIST -->", topic_list_string)

    f = open(category_relative_url + '/index.html', 'w')
    f.write(category_file_string)
    f.close()


# Function that creates the text describing the individual posts in a topic
def post_row(post_json):
    avatar_url = post_json['avatar_template']
    parsed_url = urlparse(avatar_url)
    path = parsed_url.path
    avatar_file_name = path.split('/')[-1]
    if parsed_url.netloc and parsed_url.scheme:
        pass
    elif parsed_url.netloc:
        avatar_url = base_scheme + ':' + avatar_url
    else:
        avatar_url = base_url + avatar_url
    avatar_url = avatar_url.replace('{size}', '45')
    if not os.path.exists(os.getcwd() + '/images/' + avatar_file_name):
        try:
            response = requests.get(avatar_url, stream=True, cookies=jar)
            img = Image.open(BytesIO(response.content))
            if avatar_file_name.lower().endswith('.png'):
                img = img.convert('RGBA');
            img.save(os.getcwd() + '/images/' + avatar_file_name)
        except Exception as err:
            template = "An exception of type {0} occured. Arguments:\n{1!r}"
            message = template.format(type(err).__name__, err.args)
            print('in post_row error:', 'write avatar', avatar_url, message, cnt, topic['slug'], "\n===========\n")

    post_number = post_json['post_number']
    user_name = post_json['username']
    created_at = datetime.strptime(post_json['created_at'][0:20], '%Y-%m-%dT%H:%M:%S.')
    content = post_json['cooked']

    # Since we don't generate user information,
    # replace any anchors of class mention with a span
    soup = bs(content, "html.parser")
    mention_tags = soup.findAll('a', {'class': 'mention'})
    for tag in mention_tags:
        try:
            rep = bs('<span class="mention"></span>', "html.parser").find('span')
            rep.string = tag.string
            tag.replaceWith(rep)
        except TypeError:
            pass

    img_tags = soup.findAll('img')
    for img_tag in img_tags:
        if 'src' in img_tag:
            img_url = img_tag['src']
            parsed_url = urlparse(img_url)
            path = parsed_url.path
            file_name = path.split('/')[-1]
            if parsed_url.netloc and parsed_url.scheme:
                pass
            elif parsed_url.netloc:
                img_url = base_scheme + ':' + img_url
            else:
                img_url = base_url + img_url
            try:
                response = requests.get(img_url, stream=True, cookies=jar)
                img = Image.open(BytesIO(response.content))
                if filename.lower().endswith('.png'):
                    img = img.convert('RGBA');
                img.save(os.getcwd() + '/images/' + file_name)
                img_tag['src'] = '../../images/' + file_name
            except Exception as err:
                template = "An exception of type {0} occured. Arguments:\n{1!r}"
                message = template.format(type(err).__name__, err.args)
                print('post_row', 'save image', file_name, img_url, message)
                img_tag['src'] = '../../images/missing_image.png'

    content = ''
    for s in soup.contents:
        content = content + str(s)

    post_string = '      <div class="post_container">\n'
    post_string = post_string + '        <div class="avatar_container">\n'
    post_string = post_string + '          <img src="../../images/' + avatar_file_name + '" class="avatar" />\n'
    post_string = post_string + '        </div>\n'
    post_string = post_string + '        <div class="post" id="' + str(post_number) + '">\n'
    post_string = post_string + '          <div class="user_name">' + user_name + '</div>\n'
    post_string = post_string + '          <div class="created_at">' + datetime.strftime(created_at, '%-d %b \'%y') + '</div>\n'
    post_string = post_string + '          <div class="post_content">\n'
    post_string = post_string + content + '\n'
    post_string = post_string + '          </div>\n'
    post_string = post_string + '        </div>\n'
    post_string = post_string + '      </div>\n\n'
    return post_string


# The topic_row function generates the HTML for each topic on the main page
category_url = base_url + '/categories.json?include_subcategories=true'
response = requests.get(category_url, cookies=jar)
throttle_requests()
categories_json = response.json()['category_list']['categories']
subcategories_json = [subcat for cat in categories_json if len(cat['subcategory_ids']) for subcat in cat['subcategory_list']]
allcategories_json = categories_json + subcategories_json
category_id_to_cat = dict([(cat['id'], cat) for cat in allcategories_json])
category_id_to_topics = dict([(cat['id'], []) for cat in allcategories_json])

def category_row(category_json, base_url = ''):
    category_url = base_url + 'c/' + str(category_json['id']) + '/index.html'
    
    category_html = '<div class="category-row">\n'
    category_html = category_html + '<span class="category-name">'
    category_html = category_html   + '<a href="' + category_url + '">'
    if category_json['color']:
        category_html = category_html   + '<svg fill="#' + category_json['color'] + '" class="icon" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"><rect width="24" height="24" /></svg>\n'
    category_html = category_html       + category_json['name'] + '</a>\n'
    category_html = category_html       + '<span class="category-description">\n'
    category_html = category_html       + (category_json['description'] or '') + '</span>\n'
    category_html = category_html + '</span>\n'
    category_html = category_html + '<span class="post-count">'
    category_html = category_html       + str(category_json['topics_all_time']) + '</span>\n'
    category_html = category_html + '</div>\n\n'
    return category_html



def topic_row(topic_json, base_url = ''):
    topic_url = base_url + 't/' + str(topic_json['id']) + '/index.html'
    topic_title_text = topic_json['fancy_title']
    topic_post_count = topic_json['posts_count']
    topic_pinned = topic_json['pinned_globally']
    try:
        topic_category = category_id_to_cat[topic_json['category_id']]
    except KeyError:
        topic_category = { 'name': '', 'color': '' }

    topic_html = '      <div class="topic-row">\n'
    topic_html = topic_html + '        <span class="topic">'
    if topic_pinned:
        topic_html = topic_html + '<svg class="icon" title="This was a pinned topic so it '
        topic_html = topic_html + 'appears near the top of the page." '
        topic_html = topic_html + 'xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M16 3a1 1 0 0 1 .117 1.993l-.117 .007v4.764l1.894 3.789a1 1 0 0 1 .1 .331l.006 .116v2a1 1 0 0 1 -.883 .993l-.117 .007h-4v4a1 1 0 0 1 -1.993 .117l-.007 -.117v-4h-4a1 1 0 0 1 -.993 -.883l-.007 -.117v-2a1 1 0 0 1 .06 -.34l.046 -.107l1.894 -3.791v-4.762a1 1 0 0 1 -.117 -1.993l.117 -.007h8z" /></svg>'
    topic_html = topic_html + '<a href="' + topic_url + '">'
    topic_html = topic_html + topic_title_text + '</a></span>\n'
    topic_html = topic_html + '        <span class="category">'
    if topic_category['color']:
        topic_html = topic_html + '<svg fill="#' + topic_category['color'] + '" class="icon" xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24"><rect width="24" height="24" /></svg>\n'
    topic_html = topic_html + topic_category['name'] + '</span>\n'
    topic_html = topic_html + '        <span class="post-count">'
    topic_html = topic_html + str(topic_post_count) + '</span>\n'
    topic_html = topic_html + '      </div>\n\n'
    return topic_html



# The action is just starting here.
# Check for the directory where plan to store things.
# Note that this will be overwritten!
if os.path.exists(path) and os.path.isdir(path):
    rmtree(path)
os.mkdir(path)
os.chdir(path)
os.mkdir('images')

# Grab the site title and logo - available via the basic-info API
# https://docs.discourse.org/#tag/Site/operation/getSiteBasicInfo
info_url = base_url + '/site/basic-info.json'
response = requests.get(info_url, cookies=jar)
throttle_requests()
info_json = response.json()
site_title = info_json['title']
site_logo_image_url = info_json['logo_url']
if site_logo_image_url is None:
    default_discourse_logo = b'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'
    with open(os.getcwd() + "/images/site-logo.png", "wb") as site_logo_fh:
        site_logo_fh.write(base64.decodebytes(default_discourse_logo))
else:
    parsed = urlparse(site_logo_image_url)
    if parsed.netloc == '':
        site_logo_image_url = base_url + site_logo_image_url
    response = requests.get(site_logo_image_url, stream=True, cookies=jar)
    img = Image.open(BytesIO(response.content))
    img.save(os.getcwd() + '/images/site-logo.png')
    throttle_requests()  # Seems the polite thing to do

encoded_missing_image_png = b'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'
with open(os.getcwd() + "/images/missing_image.png", "wb") as missing_image_fh:
    missing_image_fh.write(base64.decodebytes(encoded_missing_image_png))

# Write out the CSS.
f = open('archived.css', 'w')
f.write(css)
f.close()



# This is where *most* of the action happens.

# The following bit of code grabs discourse_url/latest.json to generate a list of topics.
# For each of these topics, we apply topic_row to generate a line on the main page.
# If 'more_topics_url' appears in the response, we get more.

# Note that there might be errors but the code does attempt to deal with them gracefully by
# passing over them and continuing.
#
# My archive of DiscoureMeta generated 19 errors - all image downloads that replaced with a missing image PNG.
#

# max_more_topics is the number of pages the code will load from the all topics list on your site
# You might find that you need to change max_more_topics depending on the size of your forum
max_more_topics = 99999
cnt = 0
topic_path = '/latest.json?no_definitions=true&page='
base_topic_url = base_url + topic_path
url = base_topic_url + str(cnt)
topic_list_string = ""
response = requests.get(url, cookies=jar)
topic_list = response.json()['topic_list']['topics']
for topic in topic_list:
    try:
        write_topic(topic)
        topic_list_string = topic_list_string + topic_row(topic)
        category_id_to_topics[topic['category_id']].append(topic)
    except Exception as err:
        pass
    throttle_requests()  # Seems the polite thing to do
while 'more_topics_url' in response.json()['topic_list'].keys() and cnt < max_more_topics:
    print ('cnt is ', cnt, '\n============')
    cnt = cnt + 1
    url = base_topic_url + str(cnt)
    response = requests.get(url, cookies=jar)
    topic_list = response.json()['topic_list']['topics']

    # STARTED AT 1 'CAUSE IT APPEARS THAT
    # LAST THIS = FIRST NEXT   GOTTA CHECK THAT!
    for topic in topic_list[1:]:
        topic_list_string = topic_list_string + topic_row(topic)
        write_topic(topic)
        category_id_to_topics[topic['category_id']].append(topic)
        throttle_requests()  # Seems the polite thing to do

# Wrap things up.
# Make the replacements and print the main file.
category_list_string = ""
for category_json in categories_json:
    category_list_string = category_list_string + category_row(category_json)
    write_category(category_json)

file_string = main_template \
    .replace("<!-- SITE_TITLE -->", site_title) \
    .replace("<!-- ARCHIVE_NOTICE -->", archive_notice) \
    .replace("<!-- ARCHIVE_BLURB -->", archive_blurb) \
    .replace("/* HEADER_PRIMARY_COLOR */", '#' + info_json['header_primary_color']) \
    .replace("/* HEADER_BACKGROUND_COLOR */", '#' + info_json['header_background_color']) \
    .replace("<!-- TOPIC_LIST -->", topic_list_string) \
    .replace("<!-- CATEGORY_LIST -->", category_list_string)

f = open('index.html', 'w')
f.write(file_string)
f.close()
