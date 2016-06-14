const S3Downloader = require('fastboot-s3-downloader');
const S3Notifier = require('fastboot-s3-notifier');
const FastBootAppServer = require('fastboot-app-server');

const s3Bucket = 'S3BUCKETCHANGEME';
const s3Key = 'S3KEYCHANGEME';

let downloader = new S3Downloader({
  bucket: s3Bucket,
  key: s3Key
});

let notifier = new S3Notifier({
  bucket: s3Bucket,
  key: s3Key
});

let server = new FastBootAppServer({
  downloader: downloader,
  notifier: notifier
});

server.start();
