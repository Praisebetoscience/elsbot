# Introduction

ELSbot was written to add archive.is links to submissions made from [/r/EnoughLibertarianSpam](https://reddit.com/r/EnoughLibertarianSpam) to other subreddits.  It's based on many of the other snapshot bots that frequest reddit's meta subs.

## Disclaimer

This code has been made public largely for the moderation team at /r/EnoughLibertarianSpam.  You certainly can add issues, or ask questions here or at [/r/elsbot](https://reddit.com/r/elsbot) but the author may or may not inclined to add features or debug your instance.  The author certainly will respond to any issues with may be causing problems on reddit or breaking reddit's API policies.

# Python Verson

Originally written for Python 3.4, to run on OpenShift it needed to be downgraded to python 3.3.2 

# Open Shift

This bot now runs on Open shift using the cron-1.4 and postgresql-9.2 cartridges. 

## OAuth

Login is now handled by OAuth.  [You can use this tutorial to get setup OAuth](http://praw.readthedocs.org/en/latest/pages/oauth.html), however it doesn't cover getting the refresh token which is the most important part for scripts.  To get the refresh token run `print(access_information['refresh_token'])` after step 4.

## Database

Database information is also set via Openshift environment variables: OPENSHIFT_POSTGRESQL_DB_URL and OPENSHIFT_APP_NAME.  To access the database locally you'll need to get ssh into your openshift account and run `echo ${OPENSHIFT_POSTGRESQL_DB_URL} ${OPENSHIFT_APP_NAME}` at the CLI.  You need to setup port forwarding with rhc: `rhc port-forward -a <YourAppname>`
The OpenShift database has no row limits unlike Heroku (previously used).  However, the database maintenance remains in place to for cleanliness. 

This bot was originally written for sqlite3, however there were [significant issues with using sqlite3 on Heroku](https://devcenter.heroku.com/articles/sqlite3) because of the filesystem it uses.  Now that the bot has moved over to OpenShift, the bot still uses PostgreSQL even though sqlite3 can be stored on OpenShift in OPENSHIFT_DATA_DIR simply beacuse it was eaier to migrate then change the PostArchive class again. 

# CLI

As of 2.0 the bot now supports some command line options for different deployments.

## --run-once -r

This runs a scan only once. This is useful for deploying the bot as a cron job (great on OpenShift).  The script defaults to continuous scanning. 

## --config-file -f

Allows you to specify a different config file to run the bot.  Defaults to `elsbot.cfg`.