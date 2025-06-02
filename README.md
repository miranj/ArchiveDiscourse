# ArchiveDiscourse

## About

Code for archiving a Discourse site into static HTML.

Examples of archived Discourse instances generated using this code:

- https://discuss.indiabioscience.org/ (this fork)
- https://discuss-learn.media.mit.edu/ (original behaviour)

Forked & adapted from: <https://github.com/mcmcclur/ArchiveDiscourse>, then <https://github.com/kitsandkats/ArchiveDiscourse>, and finally <https://github.com/m00k12/ArchiveDiscourse>.

See https://meta.discourse.org/t/a-basic-discourse-archival-tool/62614

## Motivation

The Discourse platform creates great forums and is rich in features.  However,
a lot of that goodness is powered by client side scripts that need to run in
order to generate each page. This has the side-effect of making it difficult to
archive a Discourse site without running and maintaining the full application
stack.

Some approaches can be used to get Discourse to provide simpler pages which are
more suitable for achiving:

- Use wget or change the User-Agent to GoogleBot to get simplified pages
- Append the parameter `print=true` to each page request to get printable versions

Unfortunately the pages returned with the above approaches are _very_ simple and
lose a lot of the richness of the original forum content.

This tool instead requests topic and post data via the Json API to Discourse and
then formats it into simplified pages containing the original 'cooked_html'
posts.  This keeps much of the content, though any custom styling made on the
Discourse server is lost and may need to be manually applied to this tools output.

## Usage

Edit the script to set at least the `base_url` variable to the root of your site
e.g. https://mysite/.  Then run the script to generate a set of HTML pages for
each topic under a new directory called `export`.

You may also wish to set `max_requests_per_min` variable to -1,
assuming your Discourse server is not subject to rate limits (set
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

Note that depending on features used on the Discourse server, the 'cooked' HTML
may contain attributes and references that are can be removed to reduce page
size a little, and also trim references to additional images.

I removed the following attributes:

    $ find . -name "index.html" -exec sed -i "s/srcset=\"[^\"]\+\"//g" {} \;
    $ find . -name "index.html" -exec sed -i "s/data-download-href=\"[^\"]\+\"//g" {} \;
    $ find . -name "index.html" -exec sed -i "s/data-small-upload=\"[^\"]\+\"//g" {} \;
    $ find . -name "index.html" -exec sed -i "s/data-base62-sha1=\"[^\"]\+\"//g" {} \;

## Nginx Configuration

### Link Redirection

This version of the tool removes the topic slugs from the URLs.  This is the topic
title part of a URL, which isn't necessary and could be wrong if a topic was renamed.
The Discourse server is clever enough to find topics by topic ID in such a case,
though that won't work for static hosting.

As a comprimise, this version of the tool outputs topics at URIs in the form
`/t/topic_id`, omitting the slug which would have been `/t/slug/topic_id`.
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

### Compression

The `index.html` files can be pre-compressed with `gzip -9`.  The gzip_static
module can then be used to server the pre-compressed files directly, or unzip
them if needed for very old clients that don't support gzip transfer.

    gzip_static  always;
    gzip_proxied expired no-cache no-store private auth;
    gunzip       on;

Note that due to how Nginx functions, an empty `index.html` file will need to
be stored alongside each `index.html.gz` file to avoid 404 errors.

See the [Nginx manual](http://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
for more details.



## Changes

- Remove Mathjax external dependency
- Add post date to post headers
- Make Avatar icons round
- Remove topic slugs
- Fix deprecation warnings
- Add post_number achors into topic pages
- ~Change default output file from index.html to archived.html~
- Add some HTML comments into templates to ease later post processing.
- Some CSS fixes to improve blockquotes and page rendering in mobile.
- Use [Poetry](https://python-poetry.org/) for dependeny management.
- Honour request rate limits when paging through topic lists.
- Add configurable rate limit (default: 100 requests per minute).
- Modernise CSS, clean up layout, improve contrast ratios, remove unused styles.
- Add archive notice to the top of all pages.
- Allow browsing by category archive pages.
- Add coloured category badges.
- Fetch site title and logo via the API, add header colours.
- Remove Font Awesome dependency.
