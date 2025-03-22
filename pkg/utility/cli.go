package utility

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

func ConfirmPrompt(message string) bool {
	fmt.Printf("%s [y/N] ", message)

	scanner := bufio.NewScanner(os.Stdin)
	if scanner.Scan() {
		input := strings.ToLower(strings.TrimSpace(scanner.Text()))
		return input == "y" || input == "yes"
	}
	return false
}
