# Introduction

ELSbot was written to add archive.today links to submissions made from [/r/EnoughLibertarianSpam](https://reddit.com/r/EnoughLibertarianSpam) to other subreddits.  It's based on many of the other snapshot bots that frequest reddit's meta subs.

## Disclaimer

This code has been made public largely for the moderation team at /r/EnoughLibtertarianSpam.  You certainly can add issues, or ask questions here or at [/r/elsbot](https://reddit.com/r/elsbot) but the author may or may not inclined to add features or debug your instance.  The author certainly will respond to any issues with may be causing problems on reddit or breaking reddit's API policies.

# Heroku

This bot is setup to run on Heroku using a Heroku postgressql developers (free) database.

## Login information

USER_NAME and PASSWORD are set as environment variables.  You can set the up via web interface or command line via this [devnote](https://devcenter.heroku.com/articles/config-vars).

## Database

Database information is also set via Heroku environment variable.  [See instructions on how to connect to the database.](https://devcenter.heroku.com/articles/heroku-postgresql#connecting-in-python)
To keep the database under the 10k row limit, it periodically removes old records.  The default retention time is 60 days, however if a sub somehow overruns this, reduce record_TTL_days as needed.

This bot was originally written for sqlite3, however there are [significant issues with using sqlite3 on Heroku](https://devcenter.heroku.com/articles/sqlite3) because of the filesystem it uses.