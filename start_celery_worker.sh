#!/usr/bin/env bash

celery -A email_service.celery worker --loglevel=info ;
