# Inscrições em Eventos do Campus

Rapid Application Development (RAD) · TSI · IFPB. Este repositório reúne três entregas sobre o mesmo sistema:

- **Ponto Extra II** — o site em HTML (seções "Contas de teste" a "Decisões de modelagem").
- **Atividade 06** — a API REST em `/api/` (seção "API REST").
- **Atividade 08** — a suíte de testes automatizados (seção "Testes automatizados").

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

| Conta | Usuário | Papel | Token da API |
|---|---|---|---|
| Uma | `admin` | Superusuário (cadastra salas pelo Admin) | `2854af2ad5f6e9e8fd6ab0bc18092954fda20c15` |
| Duas | `org_ana` | Organizadora (grupo `Organizadores`) | `3aded55fc984d147fe0c89fa725ea94906b20942` |
| Três | `org_bruno` | Organizador (grupo `Organizadores`), não altera o que é da `org_ana` | `3375b28c4e8702a21b86452c7d044d5c00d07498` |
| Quatro | `part_carla` | Participante | `ceaff1e4bb9b130c6c44d838575e7f83951f2597` |
| Cinco | `part_diego` | Participante (ocupa a última vaga do Laboratório 1) | `8dbec9cd77a45becf11e97220b7f39ece5360840` |

Os tokens valem para o `db.sqlite3` versionado. Se o banco for recriado, `popular_dados` gera tokens novos e os imprime; também é possível obtê-los com `POST /api/token/` (usuário e senha).

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
- Regras validadas no `clean()` dos models e chamadas via `full_clean()` no momento do envio, pelos formulários e por `eventos/services.py`. A inscrição em atividade roda em transação com `select_for_update` na atividade.
- Autorização: permissões do grupo `Organizadores` mais checagem de propriedade (`evento.organizador == request.user`). `is_superuser` não é usado como critério.
- Proteção por decorador (`@login_required`, `@require_POST` nas inscrições e cancelamentos) e por mixin (`LoginRequiredMixin`, `PermissionRequiredMixin` e `DonoDoEventoMixin` nas telas do organizador).

## API REST (Atividade 06)

Documentação navegável: **<http://127.0.0.1:8000/api/docs/>** (Swagger) ou `/api/redoc/`. O schema OpenAPI fica em `/api/schema/`. A API navegável do DRF responde na própria URL de cada endpoint.

Autenticação por token no cabeçalho, sem depender de sessão:

```bash
curl -X POST http://127.0.0.1:8000/api/token/ -d "username=part_carla&password=Eventos@2026"
curl -H "Authorization: Token ceaff1e4bb9b130c6c44d838575e7f83951f2597" http://127.0.0.1:8000/api/agenda/
```

### Endpoints

| Método e caminho | Quem pode | O que faz |
|---|---|---|
| `GET /api/eventos/` | Qualquer um | Lista de eventos (paginada, `?search=`, `?ordering=data_inicio`) |
| `GET /api/eventos/{id}/` | Qualquer um | Programação: o evento com as atividades, nome da sala e vagas restantes |
| `POST /api/eventos/` | Organizador | Cria evento; o organizador é o dono do token |
| `PUT/PATCH/DELETE /api/eventos/{id}/` | Organizador do evento | Altera ou exclui o próprio evento |
| `GET /api/atividades/` | Qualquer um | Lista paginada; `?search=` em título e descrição, `?ordering=inicio` ou `-inicio`, `?evento={id}` |
| `GET /api/atividades/{id}/` | Qualquer um | Uma atividade, com sala e vagas |
| `POST /api/atividades/` | Organizador do evento informado | Cria atividade |
| `PUT/PATCH/DELETE /api/atividades/{id}/` | Organizador do evento | Altera ou exclui |
| `GET /api/salas/`, `GET /api/salas/{id}/` | Qualquer um | Salas (cadastradas só pelo Admin) |
| `GET/POST /api/inscricoes-evento/` | Autenticado | Lista as próprias inscrições em eventos / inscreve-se com `{"evento": id}` |
| `DELETE /api/inscricoes-evento/{id}/` | Dono da inscrição | Cancela o evento e todas as atividades dele |
| `GET/POST /api/inscricoes-atividade/` | Autenticado | Lista as próprias / inscreve-se com `{"atividade": id}` |
| `DELETE /api/inscricoes-atividade/{id}/` | Dono da inscrição | Cancela a atividade e libera a vaga |
| `GET /api/agenda/` | Autenticado | Atividades do dono do token, de todos os eventos, por data e hora |
| `POST /api/token/` | Qualquer um | Troca usuário e senha pelo token |

Permissões: sem token, escrita devolve **401**. Com token de quem não tem o papel (participante criando atividade) ou de outro organizador, **403**. Inscrição de outra pessoa não é encontrada pelo dono do token, então devolve **404**.

### Onde as regras de negócio moram, e por quê

Escolhemos **mover a regra para um lugar que os dois caminhos enxergam**, em vez de reescrevê-la no serializer:

| Regra | Onde está | Quem chama |
|---|---|---|
| RN1 capacidade da sala | `InscricaoAtividade.clean()` em `eventos/models.py` | `services.inscrever_em_atividade` → `full_clean()` |
| RN2 conflito na agenda do participante | `InscricaoAtividade.clean()` | idem |
| RN3 sala ocupada | `Atividade.clean()` | `AtividadeForm` (site) e `AtividadeSerializer.validate` (API), ambos via `full_clean()` |
| RN4 inscrição condicionada | `services.inscrever_em_atividade` (procura a inscrição no evento) e a FK `InscricaoAtividade.inscricao_evento`, além da checagem de mesmo evento em `InscricaoAtividade.clean()` | views do site e serializer da API |
| RN5 cancelamento em cascata | `on_delete=CASCADE` em `InscricaoAtividade.inscricao_evento` | `services.cancelar_inscricao_evento` |

Como funciona:

- **Validação de dados** (RN1, RN2, RN3, período do evento, fim antes do início, inscrições fechadas, unicidade) fica no `clean()` dos models. O `ModelForm` do site chama `full_clean()` sozinho. O DRF não chama, por isso `ValidaPeloModelMixin` (`eventos/api/serializers.py`) monta a instância no `validate()` e chama o mesmo `full_clean()`. O serializer não tem nenhuma regra própria.
- **Operações de inscrição e cancelamento** ficam em `eventos/services.py`. As views do site (`eventos/views.py`) e os serializers e ViewSets da API chamam essas mesmas funções. Nenhuma das duas camadas grava uma inscrição por conta própria.
- O `ValidationError` do Django que sai do model ou do serviço vira **400 com JSON** pelo tratador `eventos/api/excecoes.py`. A mensagem é a mesma que o site mostra.

Reescrever as regras no serializer daria duas cópias de cada uma, que divergiriam no primeiro ajuste. Do jeito escolhido, uma correção no `clean()` vale para o site e para a API ao mesmo tempo.

Organizador e participante nunca vêm do JSON: `organizador` é somente leitura e é preenchido com `request.user` no `perform_create`; as inscrições não têm campo de participante, e o serviço recebe `request.user`. As vagas restantes vêm da anotação `com_vagas()` (`Count` no banco) ou de `Atividade.vagas_restantes()`.

### ViewSet ou função, e por quê

- **ViewSets com router:** `EventoViewSet`, `AtividadeViewSet`, `SalaViewSet`, `InscricaoEventoViewSet` e `InscricaoAtividadeViewSet`. São recursos com CRUD (ou parte dele) sobre um model, com lista, detalhe, paginação, busca e permissões por objeto. O ViewSet dá isso tudo e o router gera as rotas padronizadas. As inscrições usam só os mixins de listar, criar, detalhar e excluir: não faz sentido "editar" uma inscrição.
- **`@api_view`:** `agenda` (`eventos/api/views.py`). É uma leitura única, sem identificador na URL, sempre presa ao dono do token e ordenada de um jeito fixo. Não é um recurso com CRUD: um ViewSet traria rotas de detalhe e escrita que não existem aqui. A função deixa explícito que o endpoint faz uma coisa só.
- `POST /api/token/` usa o `obtain_auth_token` do DRF, que é uma `APIView`.

### O teste da seção 8

Regra escolhida: **RN1, capacidade da sala**. Com `part_carla` e `part_diego` no Treinamento de Django (Laboratório 1, capacidade 2), uma terceira conta inscrita na Semana de Tecnologia envia:

```bash
curl -X POST http://127.0.0.1:8000/api/inscricoes-atividade/ -H "Authorization: Token <token>" -H "Content-Type: application/json" -d "{\"atividade\": 2}"
```

- **Código HTTP:** `400 Bad Request`
- **Corpo:** `{"non_field_errors": ["Atividade lotada: não há mais vagas na sala."]}`
- **Onde a regra foi verificada:** `eventos/models.py`, método `InscricaoAtividade.clean()`, chamado por `full_clean()` dentro de `services.inscrever_em_atividade` (`eventos/services.py`).
- **O site usa o mesmo código?** Sim. A view `inscrever_atividade` (`eventos/views.py`) chama a mesma função `services.inscrever_em_atividade` e mostra a mesma mensagem como `messages.error`. Existe uma cópia só da regra.

### Desafio opcional: a programação em uma requisição

`GET /api/eventos/{id}/` devolve o evento, as atividades, o nome da sala e as vagas de cada uma em uma requisição, com serializers aninhados (`EventoProgramacaoSerializer` → `AtividadeNaProgramacaoSerializer`). O `prefetch_related` com `com_vagas().select_related("sala")` mantém o número de consultas fixo em 2, seja qual for a quantidade de atividades. Há um teste com `assertNumQueries` para isso.

## Requisitos pendentes

- Desafio opcional da Ponto Extra II (lista de espera): não implementado.
