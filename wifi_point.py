"""Temporary Windows Wi-Fi Direct access point owned by this process."""
import asyncio
import os
from pathlib import Path
import secrets
import subprocess

class WifiPoint:
    def __init__(self):self.process=None;self.ssid='';self.password=''
    async def start(self,ssid,password):
        if self.process and self.process.poll() is None:
            if (self.ssid,self.password)==(ssid,password):return
            await asyncio.to_thread(self.stop)
        helper=Path(__file__).with_name('assets')/'wifi-point.exe'
        if not helper.exists():raise RuntimeError('This build does not include the Wi-Fi helper.')
        self.ssid=ssid;self.password=password
        self.process=subprocess.Popen([str(helper),str(os.getpid())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding="utf-8",creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.process.stdin.write(self.ssid+'\n'+self.password+'\n');self.process.stdin.flush()
        try:
            response=await asyncio.wait_for(asyncio.to_thread(self.process.stdout.readline),20)
            if response.strip()!='READY':raise RuntimeError(response.strip() or 'The Wi-Fi link did not start.')
        except Exception:self.stop();raise
    def stop(self):
        if self.process:
            try:self.process.stdin.close();self.process.wait(timeout=3)
            except Exception:self.process.kill()
        self.process=None;self.password='';self.ssid=''
point=WifiPoint()
