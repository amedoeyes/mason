package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

var updateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update repositories",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("Update command called")
	},
}
