// Command merklecheck verifies this repository's SCITT RFC 9162 vectors with
// github.com/transparency-dev/merkle, an implementation nobody here wrote.
//
// It reads the case files of docs/upstream-package/scitt-rfc9162/v1 and asks the
// third-party verifier one question per case: do the case's own numbers verify?
// For inclusion cases that is (leaf digest, index, tree size, path) against
// root_true; for consistency cases it is (old size, new size, subproof) against
// both roots. A case must verify exactly when it claims VALID.
//
// This is the check the Python cross-checks could not make: pymerkle builds trees
// from leaf texts and never reads a path, and the Sigstore arithmetic folds
// inclusion paths only -- it carries no consistency checker at all. So the
// SUBPROOF order this package scores had no foreign verifier until this program.
//
// Not covered: leaf-text hashing is not recomputed here (that is pymerkle's job),
// and nothing here speaks to signatures, receipts or deployment.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/transparency-dev/merkle/proof"
	"github.com/transparency-dev/merkle/rfc6962"
)

type leafEntry struct {
	DigestHex string `json:"digest_hex"`
}

type caseFile struct {
	Kind              string      `json:"kind"`
	Result            string      `json:"result"`
	TreeSize          uint64      `json:"tree_size"`
	LeafIndex         uint64      `json:"leaf_index"`
	InclusionPath     []string    `json:"inclusion_path"`
	LeafEntry         *leafEntry  `json:"leaf_entry"`
	RootTrue          string      `json:"root_true"`
	ReconstructedRoot string      `json:"reconstructed_root"`
	OldSize           uint64      `json:"old_size"`
	NewSize           uint64      `json:"new_size"`
	OldRoot           string      `json:"old_root"`
	NewRoot           string      `json:"new_root"`
	ConsistencyPath   []string    `json:"consistency_path"`
	Note              string      `json:"description"`
}

type row struct {
	Case            string `json:"case"`
	Kind            string `json:"kind"`
	Result          string `json:"result"`
	ExpectValid     bool   `json:"expect_valid"`
	Verified        bool   `json:"verified"`
	AgreesOnVerdict bool   `json:"agrees_on_verdict"`
	PathLen         int    `json:"path_len"`
	Error           string `json:"error,omitempty"`
	MutatedDetected bool   `json:"mutated_detected,omitempty"`
}

var hasher = rfc6962.DefaultHasher

func decodeProof(hexParts []string) ([][]byte, error) {
	out := make([][]byte, 0, len(hexParts))
	for _, h := range hexParts {
		b, err := hex.DecodeString(h)
		if err != nil {
			return nil, fmt.Errorf("bad hex %q: %w", h, err)
		}
		out = append(out, b)
	}
	return out, nil
}

func decodeHash(s string) ([]byte, error) {
	if s == "" {
		return nil, fmt.Errorf("empty hash")
	}
	return hex.DecodeString(s)
}

func expectValid(result string) bool {
	return strings.HasPrefix(result, "VALID")
}

// mutate flips the first nibble of the first path element so the proof stops
// describing the tree it claims to describe.
func mutate(parts []string, on bool) []string {
	if !on || len(parts) == 0 {
		return parts
	}
	out := make([]string, len(parts))
	copy(out, parts)
	first := out[0]
	repl := byte('1')
	if first[0] == '1' {
		repl = '0'
	}
	out[0] = string(repl) + first[1:]
	return out
}

func checkInclusion(c caseFile, mutatePath bool) (bool, error) {
	if c.LeafEntry == nil {
		return false, fmt.Errorf("no leaf_entry")
	}
	digest, err := decodeHash(c.LeafEntry.DigestHex)
	if err != nil {
		return false, err
	}
	root, err := decodeHash(c.RootTrue)
	if err != nil {
		return false, err
	}
	path, err := decodeProof(mutate(c.InclusionPath, mutatePath))
	if err != nil {
		return false, err
	}
	if err := proof.VerifyInclusion(hasher, c.LeafIndex, c.TreeSize, digest, path, root); err != nil {
		return false, err
	}
	return true, nil
}

func checkConsistency(c caseFile, mutatePath bool) (bool, error) {
	r1, err := decodeHash(c.OldRoot)
	if err != nil {
		return false, err
	}
	r2, err := decodeHash(c.NewRoot)
	if err != nil {
		return false, err
	}
	path, err := decodeProof(mutate(c.ConsistencyPath, mutatePath))
	if err != nil {
		return false, err
	}
	if err := proof.VerifyConsistency(hasher, c.OldSize, c.NewSize, path, r1, r2); err != nil {
		return false, err
	}
	return true, nil
}

func run(dir string, mutate bool) ([]row, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		if e.IsDir() {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)

	rows := make([]row, 0, len(names))
	for _, name := range names {
		raw, err := os.ReadFile(filepath.Join(dir, name, "expected.json"))
		if err != nil {
			continue
		}
		var c caseFile
		if err := json.Unmarshal(raw, &c); err != nil {
			return nil, fmt.Errorf("%s: %w", name, err)
		}
		r := row{Case: name, Kind: c.Kind, Result: c.Result, ExpectValid: expectValid(c.Result)}
		var verified bool
		var err2 error
		switch {
		case len(c.InclusionPath) > 0 || c.LeafEntry != nil:
			r.PathLen = len(c.InclusionPath)
			verified, err2 = checkInclusion(c, mutate)
		case len(c.ConsistencyPath) > 0 || c.OldRoot != "" || c.OldSize > 0:
			r.PathLen = len(c.ConsistencyPath)
			verified, err2 = checkConsistency(c, mutate)
		default:
			continue
		}
		if !verified && err2 != nil {
			r.Error = err2.Error()
		}
		r.Verified = verified
		if mutate {
			r.MutatedDetected = !verified
		} else {
			r.AgreesOnVerdict = verified == r.ExpectValid
		}
		rows = append(rows, r)
	}
	return rows, nil
}

func main() {
	dir := flag.String("dir", "docs/upstream-package/scitt-rfc9162/v1", "case directory")
	out := flag.String("out", "", "write the JSON report here")
	selftest := flag.Bool("self-test", false, "flip one nibble of every path and require detection")
	flag.Parse()

	rows, err := run(*dir, false)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(2)
	}
	compared, agree := 0, 0
	var bad []string
	for _, r := range rows {
		compared++
		if r.AgreesOnVerdict {
			agree++
		} else {
			bad = append(bad, r.Case)
		}
	}

	type report struct {
		Contract   string `json:"contract_version"`
		ThirdParty string `json:"third_party"`
		Module     string `json:"module_version"`
		Hasher     string `json:"hasher"`
		Dir        string `json:"case_dir"`
		Total      int    `json:"cases_compared"`
		Agreements int    `json:"agrees_on_verdict"`
		Detected   int    `json:"mutated_paths_detected,omitempty"`
		Attempted  int    `json:"mutated_paths_attempted,omitempty"`
		Scope      string `json:"scope_note"`
		Rows       []row  `json:"cases"`
	}
	rep := report{
		Contract:   "uibc-scitt-go-crosscheck/1",
		ThirdParty: "github.com/transparency-dev/merkle (Google CT lineage, Apache-2.0)",
		Module:     "v0.0.2",
		Hasher:     "rfc6962.DefaultHasher (SHA-256, leaf prefix 0x00, node prefix 0x01)",
		Dir:        *dir,
		Total:      compared,
		Agreements: agree,
		Scope:      "case numbers in, verdict out: no leaf-text hashing, no signature, no receipt, no deployment claim",
		Rows:       rows,
	}

	fmt.Printf("GO THIRD-PARTY: transparency-dev/merkle %s, rfc6962/SHA-256 -> verdict %d/%d\n",
		rep.Module, agree, compared)
	if len(bad) > 0 {
		fmt.Println("  disagreements:", strings.Join(bad, ", "))
	}

	if *selftest {
		mrows, err := run(*dir, true)
		if err != nil {
			fmt.Fprintln(os.Stderr, "self-test error:", err)
			os.Exit(2)
		}
		attempted, detected := 0, 0
		var missed []string
		for _, r := range mrows {
			if (r.Result == "VALID" || strings.HasPrefix(r.Result, "VALID_BUT")) && r.PathLen > 0 {
				attempted++
				if r.MutatedDetected {
					detected++
				} else {
					missed = append(missed, r.Case)
				}
			}
		}
		rep.Attempted, rep.Detected = attempted, detected
		fmt.Printf("  self-test: %d/%d mutated VALID paths detected (empty paths excluded)\n", detected, attempted)
		if len(missed) > 0 {
			fmt.Println("  survived mutation:", strings.Join(missed, ", "))
		}
		if detected != attempted {
			fmt.Println("  SELF-TEST FAILED")
		}
	}

	if *out != "" {
		b, _ := json.MarshalIndent(rep, "", "  ")
		if err := os.WriteFile(*out, append(b, '\n'), 0o644); err != nil {
			fmt.Fprintln(os.Stderr, "write error:", err)
			os.Exit(2)
		}
		fmt.Println("  wrote", *out)
	}

	if agree != compared || (*selftest && rep.Detected != rep.Attempted) {
		os.Exit(1)
	}
	_ = sha256.New
}
