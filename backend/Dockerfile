FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY Onevo.Api.csproj ./
RUN dotnet restore Onevo.Api.csproj
COPY . ./
RUN dotnet publish Onevo.Api.csproj -c Release -o /app /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app ./
EXPOSE 8080
ENTRYPOINT ["dotnet", "Onevo.Api.dll"]
