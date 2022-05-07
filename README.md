# ArchiveDiscourse
Code for archiving a Discourse site into static HTML.

Example of an archived Discourse generated using this code: https://discuss-learn.media.mit.edu/

Forked & adapted from: https://github.com/mcmcclur/ArchiveDiscourse, and then https://github.com/kitsandkats/ArchiveDiscourse

## Usage

Edit the script to set at least the 'base_url' variable to the root of your site
e.g. https://mysite/.  Then run the script to generate a set of HTML pages for
each topic under a new directory called `export`.

You may also wish to remove the 'sleep(1)' at around line 290, assuming your
Discourse server is not subject to rate limits (set
`DISCOURSE_MAX_REQS_PER_IP_MODE: none` in the app.yml, and ensure you do not
include the template `templates/web.ratelimited.template.yml` - rebuild the app
after changing the yml if needed).

## Post Processing

The 'cooked' HTML posts on my original servers contained absolute references to
uploads on the host.  These needed additionally fetching and relocating to
static hosting to avoid still relying on the Discourse instance.

I used the following command to get a rough list of the referenced uploads:

    $ grep -ho "https://mysite/uploads/[^\", ]\+" export/t/*/index.html | sort -u > uploads.txt

I then fetched these from the original site:

    $ wget -x -i uploads.txt

The resulting directory structure and uploads can then be used to serve the
required files from a static server at the same address.

### Nginx Configuration

This version of the tool removes the topic slugs from the URLs.  This is the topic
title part of a URL, which isn't necessary and could be wrong if a topic was renamed.
The Discourse server is clever enough to find topics by topic ID in such a case,
though that won't work for static hosting.

As a comprimise, this version of the tool outputs topics at URIs in the form
`/t/topic_id', omitting the slug which would have been '/t/slug/topic_id'.
To ensure any inbound links still work, a rewrite rule such as the following
can be used with Nginx:

    rewrite ^/t/.*/([0-9]+)/?$ /t/$1 permanent;

This simply issues a 301 permanent redirection to remove the slug part of a
requested URI.

Additionally Discourse also appends post numbers into their URI scheme e.g.
`/t/slug/topic_id/post_number`.  This tool adds anchors within the single page
generated so that a rewrite rule may make incoming links work:

    rewrite ^/t/.*/([0-9]+)/([0-9]+)$ /t/$1#$2 permanent;

Both rewrite rules work together, in the following order:

    # Remove slugs and convert post_numbers in topics
    rewrite ^/t/.*/([0-9]+)/([0-9]+)$ /t/$1#$2 permanent;
    rewrite ^/t/.*/([0-9]+)/?$ /t/$1 permanent;


## Changes

- Remove Mathjax external dependency
- Add post date to post headers
- Make Avatar icons round
- Remove topic slugs
- Fix deprecation warnings
- Add post_number achors into topic pages
- Change default output file from index.html to archived.html

---
**Note**
Without topic slugs, a webserver re-write rule can be used to ensure historic
links still find topics based on topic_id, even if the topic title has been
edited or changed.
---
