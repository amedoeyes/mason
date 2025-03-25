package cmd

import (
	"context"
	"fmt"
	"os"
	"runtime"

	mason_context "github.com/amedoeyes/mason/pkg/context"
	"github.com/spf13/cobra"
)

type key string

const contextKey = key("ctx")

var version string

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
	Version: version,
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}

func init() {
	rootCmd.SetVersionTemplate(fmt.Sprintf("mason {{.Version}} %s/%s\n", runtime.GOOS, runtime.GOARCH))

	rootCmd.AddCommand(installCmd)
	rootCmd.AddCommand(listCmd)
	rootCmd.AddCommand(searchCmd)
	rootCmd.AddCommand(uninstallCmd)
	rootCmd.AddCommand(updateCmd)
	rootCmd.AddCommand(upgradeCmd)
}
