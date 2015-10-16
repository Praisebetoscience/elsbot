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

The database is back to using sqlite3, as Openshift provides the proper filesystems support.  If run locally, the location of the database file is set via the evironment variable OPENSHIFT_DATA_DIR. 

# CLI

As of 2.0 the bot now supports some command line options for different deployments.

## --run-once -r

This runs a scan only once. This is useful for deploying the bot as a cron job (great on OpenShift).  The script defaults to continuous scanning. 

## --config-file -f

Allows you to specify a different config file to run the bot.  Defaults to `elsbot.cfg`.