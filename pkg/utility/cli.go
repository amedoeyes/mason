package utility

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

func ConfirmPrompt(message string) bool {
	fmt.Printf("%s [Y/n] ", message)

	scanner := bufio.NewScanner(os.Stdin)
	if scanner.Scan() {
		input := strings.ToLower(strings.TrimSpace(scanner.Text()))
		return input == "y" || input == "yes" || input == ""
	}
	return false
}
