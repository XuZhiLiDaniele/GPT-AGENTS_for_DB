# GPT-AGENTS_for_DB
Progetto di tesi Xu Zhi Li Daniele 
Università di Bologna, Informatica per il Management.

## Required libraries:
- openai
- mysql-connector-python
- mcp
## Argomento della tesi
Sviluppare un agente accessibile che sfrutti come llm un agente locale, (gemma) e che si possa collegare ad un database. L'agente dovrà disporre degli strumenti per realizzare query al posto dell'utente per interagire con il database.

Fare un benchmark di piu llm locali, e confrontarli magari con llm commerciali non locali. Per testare capacità di aggregazione tra più database, prima relazione (es. mysql) e poi 

Sviluppare un piano di test per con query via via piu complesse.
Fare benchmark sulla latenza, ovvero velocità di esecuzione della query, e precisione, che può essere intesa come precisione rispetto alla ground truth, e la accuratezza, ovvero se almeno il formato è corretto (solo le colonne richieste).

# TO DO
- Implementare DB rimanenti ed adattare i tool e l'agente su query multi DB.
- Definire le query di testing adatte.
- Implementare testing autonomo e funzioni di memorizzazione delle metriche per valutare e confrontare il modello in termini di precisione, accuratezza e latenza.
