# Walidacja briefów

## Zasady walidacji
Brief musi zawierać:
- [ ] Jasno określony cel
- [ ] Kryteria akceptacji
- [ ] Zakres funkcjonalny
- [ ] Zależności zewnętrzne

## Przykłady

### ✅ Poprawny brief
```markdown
# Feature: Logowanie przez OAuth2

## Cel
Umożliwić użytkownikom logowanie przez Google i GitHub.

## Kryteria akceptacji
- Przycisk "Zaloguj przez Google"
- Przycisk "Zaloguj przez GitHub"
- Redirect po autoryzacji

## Zakres
- Frontend: przyciski logowania
- Backend: integracja OAuth2
```

### ❌ Niepoprawny brief
```markdown
# Feature: Lepsze logowanie

## Cel
Ulepszyć proces logowania.
```

**Braki:**
- Nieokreślone "lepsze"
- Brak kryteriów akceptacji
- Niejasny zakres

## Komenda walidacji
```bash
python -m auto_coder.validator --brief brief.md
```
