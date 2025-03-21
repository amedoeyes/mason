package utility

import (
	"os/exec"
	"runtime"
	"strings"
)

var currentTarget = map[string]bool{}

func IsPlatform(targets ...string) bool {
	for _, t := range targets {
		if currentTarget[t] {
			return true
		}
	}
	return false
}

func SelectByOS[T any](unix, windows T) T {
	if runtime.GOOS == "windows" {
		return windows
	}
	return unix
}

func detectLibC() string {
	out, err := exec.Command("getconf", "GNU_LIBC_VERSION").Output()
	if err == nil && strings.Contains(string(out), "glibc") {
		return "gnu"
	}

	out, err = exec.Command("ldd", "--version").Output()
	if err == nil {
		str := string(out)
		if strings.Contains(str, "musl") {
			return "musl"
		} else if strings.Contains(str, "glibc") || strings.Contains(str, "GNU") {
			return "gnu"
		}
	}

	return ""
}

func init() {
	os := runtime.GOOS
	arch := runtime.GOARCH

	switch os {
	case "windows":
		currentTarget["win"] = true
		switch arch {
		case "amd64":
			currentTarget["win_x64"] = true
		case "386":
			currentTarget["win_x86"] = true
		default:
			currentTarget["win_"+arch] = true
		}

	case "darwin":
		currentTarget["unix"] = true
		currentTarget["darwin"] = true
		switch arch {
		case "amd64":
			currentTarget["darwin_x64"] = true
		default:
			currentTarget["darwin_"+arch] = true
		}

	case "linux":
		currentTarget["unix"] = true
		currentTarget["linux"] = true
		env := detectLibC()
		switch arch {
		case "amd64":
			currentTarget["linux_x64"] = true
			currentTarget["linux_x64_"+env] = true
		case "386":
			currentTarget["linux_x86"] = true
			currentTarget["linux_x86_"+env] = true
		default:
			currentTarget["linux_"+arch+"_"+env] = true
		}
	}
}
