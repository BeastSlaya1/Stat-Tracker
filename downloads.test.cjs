const {test} = require('node:test');
const assert = require('node:assert/strict');
const {releaseAsset, appleLink, platforms} = require('../web-downloads/downloads.js');
const asset = {name: platforms.android.name, size: platforms.android.size, state: 'uploaded', browser_download_url: 'https://github.com/BeastSlaya1/Stat-Tracker/releases/download/v4.0.1/' + platforms.android.name};
test('published matching release enables the expected download', () => assert.equal(releaseAsset({assets:[asset]},platforms.android),asset));
test('missing, draft, wrong-sized, or substituted assets cannot enable download', () => {
 for (const release of [null, {draft:true, assets:[asset]}, {assets:[{...asset,size:1}]}, {assets:[{...asset,browser_download_url:'https://example.com/app.apk'}]}, {assets:[]}, {assets:[{...asset,state:'starter'}]}]) assert.equal(releaseAsset(release,platforms.android),null);
});
test('only real-format Apple distribution URLs are accepted', () => {
 assert.ok(appleLink('https://testflight.apple.com/join/AbCd1234'));
 assert.ok(appleLink('https://apps.apple.com/us/app/stat-tracker/id1234567'));
 for (const url of ['', 'javascript:alert(1)', 'https://evil.example/app.ipa','https://testflight.apple.com.evil.example/join/abc','http://testflight.apple.com/join/abc','https://user@testflight.apple.com/join/abc']) assert.equal(appleLink(url),null);
});
