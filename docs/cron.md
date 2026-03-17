# Cron i tryb autonomiczny

Auto-coder nie jest daemonem. Uruchamiasz go przez zewnetrzny scheduler (cron). Kazde wywolanie to
jednostkowy "tick": wybierz task, odpal, zapisz stan, wyjdz. Kolejne wywolanie kontynuuje od miejsca
gdzie poprzednie skonczylo.

## Dlaczego cron (nie daemon)?

- **Quota exhaustion:** worker moze trafic limit API w trakcie wykonywania. Cron wznowi po cooldown
  bez zarzadzania procesem.
- **Wielodniowe projekty:** taski moga trwac godziny. Cron co 20 min jest bardziej odporny niz daemon.
- **Wiele repo:** latwe dodawanie/usuwanie repo z crontab.
- **Prostota:** bez plikow PID, systemd unitow, logiki restartu.

## Produkcjyna konfiguracja crona (pelna, odporna na bledy)

```cron
*/30 * * * * /usr/bin/flock -n /tmp/myrepo-autocoder.lock bash -c \
  "cd /home/ubuntu/myrepo && rm -f .auto-coder/runner.lock && \
   env -u CLAUDECODE /home/ubuntu/.local/bin/auto-coder run --live" \
   >> /home/ubuntu/myrepo/.auto-coder/cron.log 2>&1
```

**Kluczowe elementy (po kole lekcje z boju):**

| Element | Dlaczego jest potrzebne |
|---------|------------------------|
| `flock -n /tmp/...lock` | Zapobiega rownoczesnemu uruchomieniu dwoch instancji |
| `bash -c "..."` | Pozwala na wielolinijkowe polecenie w crontab |
| `cd /repo` | Auto-coder musi byc uruchomiony z katalogu projektu |
| `rm -f runner.lock` | Czysci zombie lock po zabitym procesie |
| `env -u CLAUDECODE` | Pozwala `claude`/`ccg` dzialac wewnatrz crona |
| `~/.local/bin/auto-coder` | Pelna sciezka — cron ma ubogi PATH |
| `>> cron.log 2>&1` | Loguje output do pliku (przydatne przy debugowaniu) |

## Uproszczona konfiguracja (do testow)

Jesli debugujesz i chcesz widziec output od razu:

```cron
*/20 * * * * cd /repo && env -u CLAUDECODE auto-coder run --live
```

Ryzyko: nie ma `flock` — moze sie uruchomic kilka instancji rownoczesnie.
Ryzyko: nie ma `rm -f runner.lock` — zombie lock po zabitym procesie.

## Interwaly

| Interwal | Przypadek uzycia |
|----------|-----------------|
| 10-20 min | Rekomendowane. Szybka petla zwrotna. |
| 30 min | Produkcyjny standard. Dobry balans. |
| 60+ min | Konserwatywny. Jesli quota jest ciasny. |

## Multi-repo cron

Kazde repo dziala niezaleznie:

```cron
# Repo A: co 20 min
*/20 * * * * /usr/bin/flock -n /tmp/repoa-lock bash -c "cd /home/repoa && rm -f .auto-coder/runner.lock && env -u CLAUDECODE /home/ubuntu/.local/bin/auto-coder run --live" >> /home/repoa/.auto-coder/cron.log 2>&1

# Repo B: co 30 min
*/30 * * * * /usr/bin/flock -n /tmp/repob-lock bash -c "cd /home/repob && rm -f .auto-coder/runner.lock && env -u CLAUDECODE /home/ubuntu/.local/bin/auto-coder run --live" >> /home/repob/.auto-coder/cron.log 2>&1
```

Kazde repo ma wlasny `flock` lock wiec nie blokuja sie nawzajem.

## Alternatywa: loop mode (zamiast crona)

Jesli wolisz jeden dlugo dzialajacy proces:

```bash
auto-coder run --live --loop --max-ticks 200
```

Dziala az wszystkie taski zostana ukonczone, potem wychodzi czysto.
Przydatne dla krotkich projektow lub CI.

Ale uwaga: jesli proces zostanie zabity, bedziesz musial recznie zrestartowac.
Cron jest bezpieczniejszy — samo sie odbuduje po zabiciu procesu.

## Monitoring

```bash
# Zobacz live log
tail -f /path/to/repo/.auto-coder/cron.log

# Sprawdz PROGRESS.md (aktualizowane po kazdym ticku)
cat /path/to/repo/PROGRESS.md
# Lub na GitHub — commitowany po kazdym tasku
```

## Debugowanie crona

Jesli cron nie dziala:

1. **Sprawdz sciezke do `auto-coder`:**
   ```bash
   which auto-coder  # np. /home/ubuntu/.local/bin/auto-coder
   ```

2. **Test reczny (bez crona):**
   ```bash
   cd /repo && env -u CLAUDECODE /home/ubuntu/.local/bin/auto-coder run --live
   ```

3. **Sprawdz log:**
   ```bash
   tail -50 /repo/.auto-coder/cron.log
   ```

4. **Sprawdz czy `flock` nie blokuje:**
   ```bash
   ls -la /tmp/myrepo-autocoder.lock  # lock powinien byc usuniety po zakonczeniu
   ```

## Typowe bledy

| Bled | Przyczyna | Rozwiazanie |
|------|-----------|-------------|
| `auto-coder: not found` | Cron nie ma `auto-coder` w PATH | Uzyj pelnej sciezki |
| `already running` | Zombie `runner.lock` | Dodaj `rm -f .auto-coder/runner.lock` |
| `Manager backends unavailable` | Cron nie ma `claude` w PATH | Kod auto-coder v1.0.5+ to naprawia |
| `Task already leased` | Stale lease po przerwanym runie | Kod v1.0.5+ usuwa lease automatycznie |

## Pierwsze uruchomienie

Zanim dodasz do crona:

1. `auto-coder plan` — generuj backlog
2. `auto-coder doctor --probe-live` — sprawdz czy wszystko dziala
3. `auto-coder run --live` — jeden run testowy
4. Dopiero dodaj do crona

---

**Ostatnia aktualizacja:** 2026-03-17
**Na podstawie prawdziwych wdrozen w produkcji**
