FROM python:3.6
MAINTAINER Timo Furrer <tuxtimo@gmail.com>

ENV PYTHONUNBUFFERED 1

EXPOSE 5000

RUN mkdir -p /app
WORKDIR /app

COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
