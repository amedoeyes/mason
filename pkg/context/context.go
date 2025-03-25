package context

import (
	"os"
	"path/filepath"
	"time"

	"github.com/amedoeyes/mason/config"
	package_ "github.com/amedoeyes/mason/pkg/package"
	"github.com/amedoeyes/mason/pkg/receipt"
	"github.com/amedoeyes/mason/pkg/registry"
	"github.com/amedoeyes/mason/pkg/utility"

	"github.com/gofrs/flock"
)

type Context struct {
	Config     *config.Config
	Registries []*registry.Registry
	Packages   map[string]*package_.Package
	Receipts   map[string]*receipt.Receipt
}

func NewContext() (*Context, error) {
	ctx := &Context{}

	ctx.Config = config.NewConfig()
	if err := os.MkdirAll(ctx.Config.DataDir, 0755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(ctx.Config.PackagesDir, 0755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(ctx.Config.RegistriesDir, 0755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(ctx.Config.BinDir, 0755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(ctx.Config.ShareDir, 0755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(ctx.Config.OptDir, 0755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(ctx.Config.StagingDir, 0755); err != nil {
		return nil, err
	}

	ctx.Registries = make([]*registry.Registry, 0, len(ctx.Config.Registries))
	for _, r := range ctx.Config.Registries {
		reg, err := registry.NewRegistry(r, ctx.Config.RegistriesDir)
		if err != nil {
			return nil, err
		}
		ctx.Registries = append(ctx.Registries, reg)
	}

	ctx.Packages = map[string]*package_.Package{}
	for _, r := range ctx.Registries {
		entries, err := r.Load()
		if err != nil {
			return nil, err
		}
		for _, e := range entries {
			ctx.Packages[e.Name] = package_.NewPackage(e)
		}
	}

	ctx.Receipts = map[string]*receipt.Receipt{}
	entries, err := os.ReadDir(ctx.Config.PackagesDir)
	if err != nil {
		return nil, err
	}
	for _, entry := range entries {
		rctPath := filepath.Join(ctx.Config.PackagesDir, entry.Name(), receipt.FileName)
		exist, err := utility.PathExists(rctPath)
		if err != nil {
			return nil, err
		}
		if exist {
			rct, err := receipt.FromFile(rctPath)
			if err != nil {
				return nil, err
			}
			ctx.Receipts[rct.Name] = rct
		}
	}

	return ctx, nil
}

func (ctx *Context) AcquireLock() (*flock.Flock, error) {
	lock := flock.New(filepath.Join(os.TempDir(), "mason.lock"))
	printed := false
	for {
		locked, err := lock.TryLock()
		if err != nil {
			return nil, err
		}
		if locked {
			return lock, nil
		}
		if !printed {
			println("Another instance is running. Waiting...")
			printed = true
		}
		time.Sleep(time.Second)
	}
}
