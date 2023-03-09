#!/usr/bin/env bash

celery -A email_reading_service.celery worker --loglevel=info ;
