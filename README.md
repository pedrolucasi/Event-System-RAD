# Inscrições em Eventos do Campus

Atividade de Ponto Extra II — Rapid Application Development (RAD) · TSI · IFPB.

## Integrantes

- _Nome completo do integrante 1_
- _Nome completo do integrante 2 (se for em dupla)_

## Como executar

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

O `db.sqlite3` já vem com os dados de teste. Para recriá-los do zero:

```powershell
python manage.py migrate
python manage.py popular_dados
```

Testes automatizados das regras de negócio: `python manage.py test eventos`.

## Contas de teste

Senha de todas as contas: **`Eventos@2026`**

| Conta | Usuário | Papel |
|---|---|---|
| Uma | `admin` | Superusuário (cadastra salas pelo Admin) |
| Duas | `org_ana` | Organizadora (grupo `Organizadores`) |
| Três | `org_bruno` | Organizador (grupo `Organizadores`), não altera o que é da `org_ana` |
| Quatro | `part_carla` | Participante |
| Cinco | `part_diego` | Participante (ocupa a última vaga do Laboratório 1) |

O papel de organizador é dado pelo grupo `Organizadores`, que tem as permissões de criar, editar e excluir eventos e atividades. A conta criada pela tela de cadastro não entra em nenhum grupo, então é um participante comum.

## Dados cadastrados

### Salas

| Sala | Bloco | Capacidade |
|---|---|---|
| Auditório | Bloco Central | 100 |
| Sala 101 | Bloco A | 40 |
| **Laboratório 1** | Bloco B | **2** (sala pequena, para testar o limite) |

### Eventos

| Evento | Período | Inscrições | Organizador |
|---|---|---|---|
| Semana de Tecnologia | 09/11/2026 a 13/11/2026 | Abertas | `org_ana` |
| Jornada Científica | 11/11/2026 a 14/11/2026 | Abertas | `org_bruno` |
| Encontro de Egressos | 20/11/2026 | **Fechadas** | `org_ana` |

A Semana de Tecnologia e a Jornada Científica têm períodos que se cruzam (11 a 13/11).

### Atividades

| Evento | Atividade | Sala | Horário |
|---|---|---|---|
| Semana de Tecnologia | Abertura: o futuro da web (Palestra) | Sala 101 | 11/11 09:00–11:00 |
| Semana de Tecnologia | Treinamento de Django (Treinamento) | Laboratório 1 | 11/11 14:00–17:00 |
| Semana de Tecnologia | Treinamento de Git (Treinamento) | Sala 101 | 11/11 14:00–16:00 |
| Semana de Tecnologia | Projetos dos alunos (Apresentação) | Laboratório 1 | 12/11 09:00–11:00 |
| Jornada Científica | Ciência aberta (Palestra) | Auditório | 11/11 09:30–10:30 |
| Jornada Científica | Pôsteres de iniciação científica (Apresentação) | Auditório | 12/11 14:00–16:00 |
| Encontro de Egressos | Roda de conversa com egressos (Apresentação) | Auditório | 20/11 19:00–21:00 |

Sobreposições propositais:

- **Mesmo horário, salas distintas, mesmo evento:** Treinamento de Django (Laboratório 1) e Treinamento de Git (Sala 101), ambos em 11/11 às 14:00.
- **Mesmo horário, eventos diferentes:** Abertura (Semana, 09:00–11:00) contém por inteiro Ciência aberta (Jornada, 09:30–10:30). Um participante não consegue as duas.
- **Mesma sala, horários que não se cruzam:** Laboratório 1 com Treinamento de Django (11/11 à tarde) e Projetos dos alunos (12/11 de manhã); Sala 101 com Abertura (manhã) e Git (tarde).
- **Sala de capacidade 2:** Treinamento de Django no Laboratório 1. Com `part_carla` e `part_diego` inscritos, a terceira inscrição é recusada.

## Decisões de modelagem

- `InscricaoAtividade` aponta para `InscricaoEvento` (e não diretamente para o usuário). Assim não existe inscrição em atividade sem inscrição em evento, e o `on_delete=CASCADE` faz o cancelamento do evento remover as atividades (RN5). A validação confere que a atividade é do mesmo evento da inscrição (RN4).
- Unicidade com `UniqueConstraint`: um participante por evento e uma inscrição por atividade.
- A capacidade vem de `atividade.sala.capacidade`; vagas restantes são sempre calculadas com `Count` no banco (sem campo guardado).
- Sobreposição de intervalos: `inicio_a < fim_b and fim_a > inicio_b`. Essa única condição cobre sobreposição parcial pelos dois lados, um intervalo contendo o outro e intervalos idênticos; horários que apenas se encostam (um termina às 11:00 e o outro começa às 11:00) não conflitam.
- Regras validadas no `clean()` dos models e chamadas via `full_clean()` nas views, no momento do envio. A inscrição em atividade roda em transação com `select_for_update` na atividade.
- Autorização: permissões do grupo `Organizadores` mais checagem de propriedade (`evento.organizador == request.user`). `is_superuser` não é usado como critério.
- Proteção por decorador (`@login_required`, `@require_POST` nas inscrições e cancelamentos) e por mixin (`LoginRequiredMixin`, `PermissionRequiredMixin` e `DonoDoEventoMixin` nas telas do organizador).

## Requisitos pendentes

- Desafio opcional (lista de espera): não implementado.
