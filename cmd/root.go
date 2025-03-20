package cmd

import (
	"fmt"
	"os"

	"github.com/amedoeyes/mason/pkg/context"
	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "mason",
	Short: "Mason package manager",
	PersistentPreRun: func(cmd *cobra.Command, args []string) {
		cmd.SetContext(context.NewContext(cmd.Context()))
	},
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}

func init() {
	rootCmd.AddCommand(installCmd)
	rootCmd.AddCommand(uninstallCmd)
	rootCmd.AddCommand(upgradeCmd)
	rootCmd.AddCommand(updateCmd)
	rootCmd.AddCommand(listCmd)
	rootCmd.AddCommand(searchCmd)
}
