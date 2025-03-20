package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

var upgradeCmd = &cobra.Command{
	Use:   "upgrade [package...]",
	Short: "Upgrade packages",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("Upgrade command called with packages:", args)
	},
}
