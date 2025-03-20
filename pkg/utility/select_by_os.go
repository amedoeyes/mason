package utility

import "runtime"

func SelectByOS[T any](unix, windows T) T {
	if runtime.GOOS == "windows" {
		return windows
	}
	return unix
}
