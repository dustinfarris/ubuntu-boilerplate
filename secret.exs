use Mix.Config

# In this file, we keep production configuration that
# you likely want to automate and keep it away from
# your version control system.
config :example, Example.Endpoint,
  secret_key_base: "SECRET_KEY"

# Configure your database
config :example, Example.Repo,
  adapter: Ecto.Adapters.Postgres,
  username: "DB_USER",
  password: "DB_PASS",
  database: "example_prod",
  pool_size: 20
