# Changelog

## 0.2.0 (2026-11-19)

- **Preview** now shows the feature as it would regenerate with the candidate (for example the fillet applied to the suggested edge). It is computed in a throwaway transaction, so nothing in the document changes.
- New **Highlight** button shows the candidate on the geometry before the feature (for example the edge on the Pad), with later features hidden and a red ring where the old element was.
- Candidate rows have both buttons. Card buttons wrap when the panel is narrow.

## 0.1.1 (2026-11-19)

- Fixed: the Resolve_Mode preferences group showed FeatureNamer's page. The page class now has a unique name, because FreeCAD identifies Python preference pages by class name.

## 0.1.0 (2026-11-19)

First release.

- Panel listing broken PartDesign references: missing edges and faces in link properties, and broken sketch attachments.
- Geometric fingerprints of referenced elements, stored while the model is healthy and saved with the file.
- Similarity scoring with suggest, ambiguous and none outcomes, and adjustable thresholds.
- Preview in the 3D view, Accept, Accept all suggested, Show candidates, Pick in 3D view, Resolve manually.
- Auto mode (on by default) opens the panel after a recompute that breaks something, with a toggle in the panel.
- Sketch attachment fallback that works without stored fingerprints.
