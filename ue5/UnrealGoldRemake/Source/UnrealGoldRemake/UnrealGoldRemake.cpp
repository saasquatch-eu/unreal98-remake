#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogUnrealGoldRemake, Log, All);

class FUnrealGoldRemakeModule final : public FDefaultGameModuleImpl
{
public:
    virtual void StartupModule() override
    {
        UE_LOG(LogUnrealGoldRemake, Display, TEXT("UnrealGoldRemake primary C++ module loaded."));
    }
};

IMPLEMENT_PRIMARY_GAME_MODULE(FUnrealGoldRemakeModule, UnrealGoldRemake, "UnrealGoldRemake");
