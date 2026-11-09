# Initial seed provenance

This seed contains 14 cofactor entities: six coenzymes, three prosthetic groups
and five metal ions. There are 28 ingredient supply links, 12 pathway links,
14 PTM requirement-concept links and three additional named enzyme-example links.
Supply describes chemical composition or a documented precursor relationship;
it does not establish uptake, bioavailability, physiological occupancy or a
universal organism requirement.

## Candidate accounting

`curation/mim_candidates.tsv` inventories every record whose current
`nutritional_roles` contains COFACTOR_PROVIDER, VITAMIN_SOURCE or TRACE_ELEMENT at
MIM commit `0529fc6bc065bfa04aba0aed234f6b0cfad6a142`. It retains 162 unique paths:
four cofactor-provider records, 57 vitamin-source records and 101 trace-element
records. Calcium_Pantothenate carries two vitamin-source assertions, yielding
58 assertions. The requested eight cofactor providers were not reproduced.
Historical TRACE_ELEMENT text in Kbr, Ki, Licl, Nabr and Naf was excluded because
those records currently carry MINERAL_SOURCE. Role assignment alone was never
used to establish cofactor activity.

Twenty-eight candidates have curated supplier links. The remaining 134 are
explicitly deferred: 30 formulations/mixtures, 38 vitamins or precursors,
53 metal/nonmetal candidates, 12 chemical identities and one cofactor chemistry
case. These are research dispositions, not claims that the candidates lack
biological activity. Haemin (CHEBI:50385) remains deferred: chloridoiron(III)
chemistry is not substituted for ferroheme, ferriheme or an unspecified heme
requirement. Generic cobalamin is not substituted for methyl/adenosylcobalamin.

MIM issue 1265 was open and main still matched the cited revision when checked
on 2026-11-08. Every MIM link is PROVISIONAL and retains the actual legacy ID plus
source path; paths distinguish duplicate chemical IDs. Adopt stable MIM IDs only
from an actual published migration, preserving this earlier provenance.

## Sources and attribution

The CultureBotAI repository authors and their cited contributors supply the
source records. Each link names the exact immutable file and commit:

| Corpus | Commit | Licence source |
| --- | --- | --- |
| MIM | `0529fc6bc065bfa04aba0aed234f6b0cfad6a142` | [MIM LICENSE](https://github.com/CultureBotAI/MediaIngredientMech/blob/0529fc6bc065bfa04aba0aed234f6b0cfad6a142/LICENSE) |
| PathwayMech | `9584009d49579267233124f4a1057b9425a007d9` | [PathwayMech LICENSE](https://github.com/CultureBotAI/PathwayMech/blob/9584009d49579267233124f4a1057b9425a007d9/LICENSE) |
| ProteinTraitsMech | `8d08b33cfbee1e9d1c2fdb2211b82b49dd0c8b1f` | [ProteinTraitsMech LICENSE](https://github.com/CultureBotAI/proteintraitsmech/blob/8d08b33cfbee1e9d1c2fdb2211b82b49dd0c8b1f/LICENSE) |

Their project-authored scientific data are CC-BY-4.0; source-specific terms remain
applicable to third-party content. Chemical facts and relations come from the
[ChEBI team at EMBL-EBI](https://www.ebi.ac.uk/chebi/about), whose data are CC-BY-4.0.
Protein annotations and the thiamine keyword come from the
[UniProt Consortium](https://rest.uniprot.org/help/license), also CC-BY-4.0.
These terms were inspected on 2026-11-08 before reuse. Our derived records,
candidate accounting and selected factual projections use CC-BY-4.0; see
[LICENSE-DATA](../../LICENSE-DATA). Source prose was paraphrased; the few retained
short definitions are identified as excerpts. No upstream corpus is republished
wholesale. MetaCyc identifiers/ordering are attributed via the cited PathwayMech
records; no MetaCyc database or literature text is redistributed.

## Evidence scope

`seed_sources.json` retains 232 selected source projections with original source
byte SHA-256, source URL, licence and either exact commit/path or retrieval time.
For live databases, ChEBI `modified_on` and UniProt `entryAudit` preserve their
reported versions. A projection omits fields; its original-source digest does
not purport to be a digest of the projected JSON, a signature or proof of source
authenticity. JSON Pointer locators in records resolve against each projection's
`data` object. Pathway edge indices and UniProt comment indices retain their
original positions. Omitted narrative is not silently reconstructed.

The bounded pathway search covered all 282 YAMLs under `data/pathways` at the
cited commit; the untruncated GitHub tree SHA is recorded in the source index.
Only linked pathways are projected. Copper's exact Cu(2+) occurrences were not
cofactor dependencies; the broader copper-cation SOD1 annotation was not treated
as identity. No exact cobalamin pathway endpoint was asserted. Several pathways
use a different conjugate form from the ingredient and seed: those links name
`target_chemical_id` and explicit `CONJUGATE_FORM_*` relations, backed by ChEBI
conjugate edges. CoM's native MetaCyc ID uses ChEBI's explicit cross-reference.

PTM requirement concepts are conceptual coverage, not organism measurements.
Three enzyme links are restricted to a named canonical exemplar in an actual
PTM enzyme-class record, corroborated by that protein's UniProt annotation:

| Seed | Exemplar | Evidence level retained |
| --- | --- | --- |
| FAD | P00363, E. coli K-12 fumarate reductase | UniProt cofactor note cites ECO:0000269 experimental evidence and PMIDs 10373108, 24374335, 26644464 |
| FMN | P38075, S. cerevisiae pyridoxine/pyridoxamine 5'-phosphate oxidase | Issuing-database cofactor annotation without explicit experimental evidence code |
| Thiamine diphosphate | P83779, C. albicans pyruvate decarboxylase | ECO:0000250 by similarity to P06169 |

These links do not assert that every EC-class member requires that cofactor.
The cobalt pathway context is alternative in vitro Ald2 reconstitution, the
manganese SOD2 annotation is by similarity, and nickel is scoped to the retained
AllA assay. The records preserve these limitations.

## Maintenance and checks

`just audit-seed` checks retained source identifiers, commits, locators, selected
pathway edges, conjugate relationships, named enzyme cofactors and complete
candidate accounting offline. It does not assess scientific truth or rerun a
complete upstream search. CI runs this check and corruption tests through
`just check`. The authored records are maintained directly with `just new-history`;
the TSV and source index are maintained provenance inputs, not hidden generated
owners. Replacing a source projection requires rechecking every affected claim
and preserving provenance. A future source release is a new curation task.
