#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import fuse
import stat
import errno
from dbclient import dbclient
import re
from time import time

if not hasattr(fuse, "__version__"):
	raise RuntimeError("No fuse.__version__, too old?")
fuse.fuse_python_api = (0, 2)
NOTFOUND = IOError(errno.ENOENT, "Not found")
md5re = re.compile(r"^([0-9a-f]{32})\.\w+$")
sre = re.compile(r"[ /]")

class WpStat(fuse.Stat):
	def __init__(self, mode, nlink):
		self.st_mode = mode
		self.st_ino = 0
		self.st_dev = 0
		self.st_nlink = nlink
		self.st_uid = 0
		self.st_gid = 0
		self.st_size = 0
		self.st_atime = 0
		self.st_mtime = 0
		self.st_ctime = 0

class Cache:
	def __init__(self, ttl):
		self._data = {}
		self._time = time()
		self._ttl  = ttl

	def get(self, key, getter):
		if self._time < time() - self._ttl:
			self.clean()
		if key not in self._data:
			self._data[key] = (time(), getter(key))
		return self._data[key][1]

	def clean(self):
		self._time = time()
		t = self._time - self._ttl
		for key in self._data.keys():
			if self._data[key][0] < t:
				del self._data[key]

class Wellpapp(fuse.Fuse):
	def __init__(self, *a, **kw):
		self._cache = Cache(30)
		self._client = dbclient()
		fuse.Fuse.__init__(self, *a, **kw)

	def getattr(self, path):
		search = self._path2search(path)
		path = path.split("/")[1:]
		if md5re.match(path[-1]):
			mode = stat.S_IFLNK | 0444
			nlink = 1
		elif path == [""] or search:
			mode = stat.S_IFDIR | 0555
			nlink = 2
			if search:
				try:
					self._cache.get(search, self._search)
				except Exception:
					raise NOTFOUND
		else:
			raise NOTFOUND
		return WpStat(mode, nlink)

	def readlink(self, path):
		path = path.split("/")[1:]
		m = md5re.match(path[-1])
		if m:
			return self._client.image_path(m.group(1))
		raise NOTFOUND

	def readdir(self, path, offset):
		list = [".", ".."]
		search = self._path2search(path)
		if path != "/" and not search: raise NOTFOUND
		if search:
			try:
				list += self._cache.get(search, self._search)
			except Exception:
				raise NOTFOUND
		for e in list:
			yield fuse.Direntry(e)

	def _search(self, search):
		s = self._client.search_post(tags=search[0],
		                             excl_tags=search[1],
		                             wanted=["ext"])
		r = []
		for m in s:
			r.append(m + "." + s[m]["ext"])
		return map(str, r)

	def _path2search(self, path):
		if path == "/": return None
		want = []
		dontwant = []
		for e in sre.split(path[1:]):
			if e[0] == "-":
				dontwant.append(e[1:])
			else:
				want.append(e)
		return tuple(want), tuple(dontwant)

server = Wellpapp(dash_s_do = "setsingle")
server.parse(errex = 1)
server.main()
