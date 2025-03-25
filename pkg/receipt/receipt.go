package receipt

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/amedoeyes/mason/pkg/package"
	"github.com/amedoeyes/mason/pkg/utility"
	"github.com/package-url/packageurl-go"
)

const FileName = "mason-receipt.json"

type Receipt struct {
	Name          string        `json:"name"`
	PrimarySource PrimarySource `json:"primary_source"`
	Links         Links         `json:"links"`
}

type PrimarySource struct {
	ID   string                `json:"id"`
	PURL packageurl.PackageURL `json:"-"`
}

type Links struct {
	Bin   map[string]string `json:"bin"`
	Share map[string]string `json:"share"`
	Opt   map[string]string `json:"opt"`
}

func FromFile(path string) (*Receipt, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var r Receipt
	if err := json.Unmarshal(data, &r); err != nil {
		return nil, err
	}
	purl, err := packageurl.FromString(r.PrimarySource.ID)
	if err != nil {
		return nil, err
	}
	r.PrimarySource.PURL = purl
	return &r, nil
}

func FromPackage(p *package_.Package, dir, shareDir, optDir string) (*Receipt, error) {
	share := map[string]string{}
	if p.Share != nil {
		for dest, src := range *p.Share {
			res, err := utility.ResolveForSymLink(filepath.Join(dir, src), filepath.Join(shareDir, dest))
			if err != nil {
				return nil, err
			}
			for dest, src := range res {
				relDest, err := filepath.Rel(shareDir, dest)
				if err != nil {
					return nil, err
				}
				relSrc, err := filepath.Rel(dir, src)
				if err != nil {
					return nil, err
				}
				share[relDest] = relSrc
			}
		}
	}

	opt := map[string]string{}
	if p.Opt != nil {
		for dest, src := range *p.Opt {
			res, err := utility.ResolveForSymLink(filepath.Join(dir, src), filepath.Join(optDir, dest))
			if err != nil {
				return nil, err
			}
			for dest, src := range res {
				relDest, err := filepath.Rel(optDir, dest)
				if err != nil {
					return nil, err
				}
				relSrc, err := filepath.Rel(dir, src)
				if err != nil {
					return nil, err
				}
				opt[relDest] = relSrc
			}
		}
	}

	return &Receipt{
		Name: p.Name,
		PrimarySource: PrimarySource{
			ID:   p.Source.PURL.ToString(),
			PURL: p.Source.PURL,
		},
		Links: Links{
			Bin:   p.ResolveBin(),
			Share: share,
			Opt:   opt,
		},
	}, nil
}

func (r *Receipt) Write(dir string) error {
	jsonData, err := json.Marshal(r)
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(dir, FileName), jsonData, 0644); err != nil {
		return err
	}
	return nil
}
