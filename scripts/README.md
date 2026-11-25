# README figures

The profile README is made of SVG figures in `assets/`. They are generated, so
edit the content in `build_figures.py` and rebuild:

```sh
pip install -r scripts/requirements.txt
python3 scripts/build_figures.py
```

The contributions figure needs `data/contributions.json`. The
`Refresh README figures` workflow fetches it once a day with
`fetch_contributions.py`, rebuilds, and commits the result. To run it by hand:

```sh
GITHUB_TOKEN=<token> GITHUB_LOGIN=<user> python3 scripts/fetch_contributions.py
```

## Credits

- Colours: Glacier Night Vivid, from the `setup` repo.
- Fonts in `fonts/`, each under the SIL Open Font License 1.1 (see the `OFL-*.txt`
  files): Bricolage Grotesque, Hanken Grotesk, JetBrains Mono.
- Brand logos in `icons.json`: [Simple Icons](https://simpleicons.org) (CC0).
  The logos are trademarks of their owners.
- Outline icons in `icons.json`: [Lucide](https://lucide.dev) (ISC).
