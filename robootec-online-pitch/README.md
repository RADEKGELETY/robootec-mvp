# ROBOOTEC.AI Online Pitch

Statická webová verze pitch decku s přesným pořadím slidů, textovým scénářem a hlasovým doprovodem.

## Spuštění lokálně

```bash
cd /Users/radekgelety/Documents/Playground/robootec-online-pitch
python3 -m http.server 4173
```

Pak otevři [http://localhost:4173](http://localhost:4173).

## Doporučené publikování

Nejrychlejší profesionální varianty:

1. Vercel: přetáhnout složku projektu nebo napojit Git repo.
2. Netlify: deploy celé složky jako static site.
3. GitHub Pages: nahrát projekt do repozitáře a publikovat branch.

## Co web umí

- Každý slide je samostatná sekce s vlastním anchor odkazem.
- U každého slidu je přesný text `Co říct`.
- Hlasový režim používá browser `speechSynthesis` a preferuje mužský hlas, pokud je v systému dostupný.
