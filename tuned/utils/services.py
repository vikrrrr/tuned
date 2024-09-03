import os
import subprocess
import re
import stat
from tuned.utils.commands import commands

_cmd = commands()
_services = None

class ServicesBase:
	def enable(self, name: str) -> bool:
		raise NotImplementedError()

	def disable(self, name: str) -> bool:
		raise NotImplementedError()

	def is_enabled(self, name: str) -> bool:
		raise NotImplementedError()

	def restart(self, name: str) -> bool:
		raise NotImplementedError()

	def is_system_stopping(self) -> bool:
		raise NotImplementedError()

class NoopServices(ServicesBase):
	def enable(self, name: str) -> bool:
		return True

	def disable(self, name: str) -> bool:
		return True

	def is_enabled(self, name: str) -> bool:
		return True

	def restart(self, name: str) -> bool:
		return True

	def is_system_stopping(self) -> bool:
		return False

class SystemDServices(ServicesBase):
	def enable(self, name: str) -> bool:
		return _exec(["systemctl", "enable", name])

	def disable(self, name: str) -> bool:
		return _exec(["systemctl", "disable", name])

	def is_enabled(self, name: str) -> bool:
		return _exec(["systemctl", "is-enabled", name])

	def restart(self, name: str) -> bool:
		return _exec(["systemctl", "restart", name, "-q"])

	def is_system_stopping(self) -> bool:
		retcode, out = _cmd.execute(["systemctl", "is-system-running"])
		if retcode < 0:
			return False
		if out[:8] == "stopping":
			return False
		retcode, out = _cmd.execute(["systemctl", "list-jobs"])
		return re.search(r"\b(shutdown|reboot|halt|poweroff)\.target.*start", out) is None and not retcode

class RunitServices(ServicesBase):
	def enable(self, name: str) -> bool:
		try:
			if not self.is_enabled(name):
				os.symlink(f"/etc/sv/{name}", f"/var/service/{name}", target_is_directory=True)
			return True
		except:
			return False

	def disable(self, name: str) -> bool:
		try:
			if self.is_enabled(name):
				os.remove(f"/var/service/{name}")
			return True
		except:
			return False

	def is_enabled(self, name: str) -> bool:
		return (os.path.exists(f"/var/service/{name}") and
			not os.path.exists(f"/var/service/{name}/down"))

	def restart(self, name: str) -> bool:
		return _exec(["sv", "restart", name])

	def is_system_stopping(self) -> bool:
		try:
			mode = os.stat("/etc/runit/stopit").st_mode
			return (stat.S_IXUSR & mode) != 0
		except:
			return False

def _exec(args: list[str], rc: list[int] = [0]) -> bool:
	try:
		return subprocess.call(args) in rc
	except:
		return False

def services() -> ServicesBase:
	global _services
	if _services is None:
		if _exec(["systemctl", "status"]):
			_services = SystemDServices()
		elif _exec(["sv"], rc = [100]):
			_services = RunitServices()
		else:
			_services = NoopServices()
	return _services
