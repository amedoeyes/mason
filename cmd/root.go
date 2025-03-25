package cmd

import (
	"context"
	"fmt"
	"os"

	mason_context "github.com/amedoeyes/mason/pkg/context"
	"github.com/spf13/cobra"
)

type key string

const contextKey = key("ctx")

var rootCmd = &cobra.Command{
	Use:   "mason",
	Short: "Mason package manager",
	PersistentPreRun: func(cmd *cobra.Command, args []string) {
		ctx, err := mason_context.NewContext()
		if err != nil {
			panic(err)
		}
		cmd.SetContext(context.WithValue(cmd.Context(), contextKey, ctx))
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
